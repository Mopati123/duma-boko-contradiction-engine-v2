#!/usr/bin/env python3
"""
Temporal Discovery Strategy Upgrade v2.

Converts temporal expansion seeds into targeted source-specific discovery
strategy candidates. Live probing attempts public metadata discovery only; this
lane never invents URLs, creates quotes, timestamps, claims, contradictions,
proof chains, final reports, production readiness, or approved evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse
import hashlib
import http.client
import html
import json
import re
import urllib.error
import urllib.request


DEFAULT_TEMPORAL_SEEDS = Path(
    "outputs/temporal_evidence_expansion_seeds/temporal_expansion_seeds.json"
)
DEFAULT_TEMPORAL_WEB_SUMMARY = Path(
    "outputs/temporal_web_source_discovery/temporal_web_discovery_summary.json"
)
DEFAULT_TEMPORAL_WEB_REFUSALS = Path(
    "outputs/temporal_web_source_discovery/temporal_web_discovery_refusals.json"
)
DEFAULT_SOURCE_REGISTRY = Path("inputs/source_registry/duma_boko_source_registry.json")

DEFAULT_OUTPUT_DIR = Path("outputs/temporal_discovery_strategy_upgrade")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_strategy_summary.json"
CANDIDATES_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_strategy_candidates.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_strategy_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_strategy_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_strategy_schema.json"

SCHEMA_VERSION = "temporal_discovery_strategy_upgrade_v2"
SOURCE_REGISTRY_VERSION = "canonical_source_registry_engine_v2"

CANDIDATE_STATUS = "TEMPORAL_DISCOVERY_STRATEGY_CANDIDATE"
PARTIAL_STATUS = "TEMPORAL_DISCOVERY_STRATEGY_PARTIAL"
REFUSED_STATUS = "TEMPORAL_DISCOVERY_STRATEGY_REFUSED"

TEMPORAL_WEB_STATUSES = (
    "TEMPORAL_WEB_SOURCE_DISCOVERY_DRY_RUN_VALIDATED",
    "TEMPORAL_WEB_SOURCE_DISCOVERY_CANDIDATE",
    "TEMPORAL_WEB_SOURCE_DISCOVERY_PARTIAL",
    "TEMPORAL_WEB_SOURCE_DISCOVERY_REFUSED",
)

TIME_DIRECTIONS = ("BEFORE", "AFTER")
TARGET_EVIDENCE_TYPES = (
    "CAMPAIGN_PROMISE",
    "MANIFESTO",
    "RALLY_SPEECH",
    "INTERVIEW",
    "OFFICIAL_GOVERNMENT_STATUS",
    "MINISTRY_UPDATE",
    "BUDGET_ACTION",
    "PARLIAMENT_RECORD",
    "NEWS_FOLLOWUP",
)

VERIFICATION_STATUSES = (
    "TEMPORAL_STRATEGY_DEMO_UNVERIFIED",
    "VERIFIED_REACHABLE_TEMPORAL_ENDPOINT",
    "DISCOVERED_REQUIRES_MANUAL_REVIEW",
    "REFUSED_NO_PUBLIC_RESULT",
    "REFUSED_UNREACHABLE",
    "REFUSED_METADATA_UNVERIFIED",
    "REFUSED_SEARCH_UNAVAILABLE",
)

REFUSAL_CODES = (
    "REFUSED_NO_PUBLIC_RESULT",
    "REFUSED_UNREACHABLE",
    "REFUSED_METADATA_UNVERIFIED",
    "REFUSED_SEARCH_UNAVAILABLE",
)

BEFORE_STRATEGIES = (
    ("before_mmegi_manifesto", 'site:mmegi.bw "Duma Boko" "manifesto"'),
    ("before_sundaystandard_promise", 'site:sundaystandard.info "Duma Boko" "promise"'),
    ("before_gazette_campaign", 'site:thegazette.news "Duma Boko" "campaign"'),
    ("before_youtube_rally", 'site:youtube.com "Duma Boko" "rally"'),
    ("before_facebook_udc", 'site:facebook.com "Duma Boko" "UDC"'),
    ("before_udc_manifesto", '"Umbrella for Democratic Change manifesto"'),
    ("before_duma_boko_2024_campaign_promise", '"Duma Boko 2024 campaign promise"'),
)

AFTER_STRATEGIES = (
    ("after_gov_bw_duma_boko", 'site:gov.bw "Duma Boko"'),
    ("after_dailynews_duma_boko", 'site:dailynews.gov.bw "Duma Boko"'),
    ("after_mmegi_government", 'site:mmegi.bw "Duma Boko" "government"'),
    ("after_gazette_president", 'site:thegazette.news "Duma Boko" "President"'),
    ("after_government_update", '"Duma Boko government update"'),
    ("after_ministry_update", '"Duma Boko ministry update"'),
    ("after_budget_allocation", '"Duma Boko budget allocation"'),
)

TEMPORAL_SEED_FIELDS = (
    "temporal_seed_id",
    "source_claim_id",
    "normalized_claim_id",
    "subject",
    "predicate",
    "object",
    "time_direction",
    "target_evidence_type",
    "search_query",
    "expected_topic",
    "expected_claim_keywords",
    "reasoning_summary",
    "manual_review_required",
    "seed_root",
)

TEMPORAL_SEED_LINEAGE_FIELDS = (
    "temporal_seed_id",
    "source_claim_id",
    "normalized_claim_id",
    "packet_id",
    "source_url",
    "source_owner",
    "source_title",
    "evidence_anchors",
    "evidence_hashes",
    "claim_root",
    "packet_root",
    "normalized_claim_root",
    "lineage_root",
)

CANDIDATE_FIELDS = (
    "temporal_strategy_candidate_id",
    "temporal_seed_id",
    "normalized_claim_id",
    "source_claim_id",
    "time_direction",
    "target_evidence_type",
    "strategy_name",
    "query",
    "candidate_url",
    "source_title",
    "source_owner",
    "http_status",
    "content_type",
    "verification_status",
    "manual_review_required",
    "metadata_hash",
    "candidate_root",
)

REFUSAL_FIELDS = (
    "temporal_strategy_refusal_id",
    "temporal_seed_id",
    "normalized_claim_id",
    "source_claim_id",
    "time_direction",
    "target_evidence_type",
    "strategy_name",
    "query",
    "candidate_url",
    "seed_root",
    "http_status",
    "content_type",
    "refusal_code",
    "refusal_reason",
    "manual_review_required",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "refusal_root",
)

LINEAGE_FIELDS = (
    "temporal_seed_id",
    "normalized_claim_id",
    "source_claim_id",
    "seed_root",
    "temporal_strategy_candidate_id",
    "candidate_root",
    "temporal_strategy_refusal_id",
    "refusal_root",
    "lineage_root",
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


def _source_owner_from_url(value: str) -> str:
    return urlparse(value.strip()).netloc.lower()


def _duckduckgo_url(query: str) -> str:
    return f"https://duckduckgo.com/html/?q={quote_plus(query)}"


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


def _seed_root_material(seed: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(seed)
    material.pop("seed_root", None)
    return material


def _candidate_metadata_material(candidate: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field_name: candidate[field_name]
        for field_name in CANDIDATE_FIELDS
        if field_name not in ("metadata_hash", "candidate_root")
    }


def _candidate_root_material(candidate: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(candidate)
    material.pop("candidate_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _lineage_root_material(lineage: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(lineage)
    material.pop("lineage_root", None)
    return material


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "temporal_discovery_strategy_upgrade_only": True,
        "modes": ["dry-run", "probe-web"],
        "temporal_web_upstream_statuses": list(TEMPORAL_WEB_STATUSES),
        "candidate_fields": list(CANDIDATE_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "lineage_fields": list(LINEAGE_FIELDS),
        "verification_statuses": list(VERIFICATION_STATUSES),
        "refusal_codes": list(REFUSAL_CODES),
        "before_strategies": [
            {"strategy_name": name, "query": query} for name, query in BEFORE_STRATEGIES
        ],
        "after_strategies": [
            {"strategy_name": name, "query": query} for name, query in AFTER_STRATEGIES
        ],
        "discovery_policy": (
            "Dry-run emits targeted strategy probe candidates only. Probe-web "
            "uses cached DuckDuckGo HTML searches and verifies first-result "
            "metadata where available. Search result pages may be manual-review "
            "candidates but are never verified temporal evidence."
        ),
        "prohibited_outputs": {
            "evidence_invented": 0,
            "urls_invented": 0,
            "quotes_created": 0,
            "quotes_invented": 0,
            "timestamps_created": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
        },
        "root_rules": {
            "metadata_hash": "sha256 over candidate metadata excluding metadata_hash and candidate_root",
            "candidate_root": "sha256 over candidate excluding candidate_root",
            "refusal_root": "sha256 over refusal excluding refusal_root",
            "lineage_root": "sha256 over strategy lineage excluding lineage_root",
            "temporal_strategy_root": (
                "sha256 over sorted candidate roots, sorted refusal roots, sorted "
                "lineage roots, and closed guardrail counters"
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
        raise ValueError("temporal strategy schema_version changed unexpectedly")
    if schema.get("candidate_fields") != list(CANDIDATE_FIELDS):
        raise ValueError("temporal strategy candidate fields changed unexpectedly")
    if schema.get("refusal_fields") != list(REFUSAL_FIELDS):
        raise ValueError("temporal strategy refusal fields changed unexpectedly")
    if schema.get("verification_statuses") != list(VERIFICATION_STATUSES):
        raise ValueError("temporal strategy verification statuses changed unexpectedly")


def _load_temporal_seeds(payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not payload:
        raise ValueError("temporal_expansion_seeds.json is missing")
    seeds = payload.get("temporal_expansion_seeds")
    if not isinstance(seeds, list):
        raise ValueError("temporal_expansion_seeds must be a list")
    lineage = payload.get("temporal_seed_lineage", [])
    if lineage is None:
        lineage = []
    if not isinstance(lineage, list):
        raise ValueError("temporal_seed_lineage must be a list when present")
    return seeds, lineage


def validate_temporal_seed(seed: Dict[str, Any]) -> None:
    if set(seed.keys()) != set(TEMPORAL_SEED_FIELDS):
        raise ValueError("Temporal seed fields changed unexpectedly")
    for field_name in (
        "temporal_seed_id",
        "source_claim_id",
        "normalized_claim_id",
        "subject",
        "predicate",
        "object",
        "time_direction",
        "target_evidence_type",
        "search_query",
        "expected_topic",
        "reasoning_summary",
        "seed_root",
    ):
        _require_nonempty_string(seed, field_name, "TemporalSeed")
    if seed["time_direction"] not in TIME_DIRECTIONS:
        raise ValueError(f"Unsupported time_direction: {seed['time_direction']}")
    if seed["target_evidence_type"] not in TARGET_EVIDENCE_TYPES:
        raise ValueError(f"Unsupported target_evidence_type: {seed['target_evidence_type']}")
    if not isinstance(seed.get("expected_claim_keywords"), list) or not seed[
        "expected_claim_keywords"
    ]:
        raise ValueError("TemporalSeed.expected_claim_keywords must be non-empty")
    if seed["manual_review_required"] is not True:
        raise ValueError("TemporalSeed.manual_review_required must remain true")
    if not _is_nonzero_hash(seed["seed_root"]):
        raise ValueError("TemporalSeed.seed_root must be non-zero")
    if seed["seed_root"] != _hash_json(_seed_root_material(seed)):
        raise ValueError(f"seed_root mismatch for {seed['temporal_seed_id']}")


def _validate_seed_lineage(
    seeds: List[Dict[str, Any]],
    lineage_records: List[Dict[str, Any]],
) -> None:
    if not lineage_records:
        return
    seed_ids = {seed["temporal_seed_id"] for seed in seeds}
    lineage_ids = set()
    for lineage in lineage_records:
        if set(lineage.keys()) != set(TEMPORAL_SEED_LINEAGE_FIELDS):
            raise ValueError("Temporal seed lineage fields changed unexpectedly")
        _require_nonempty_string(lineage, "temporal_seed_id", "TemporalSeedLineage")
        if lineage["temporal_seed_id"] not in seed_ids:
            raise ValueError("Temporal seed lineage references unknown temporal_seed_id")
        if lineage["temporal_seed_id"] in lineage_ids:
            raise ValueError("Temporal seed lineage temporal_seed_id values must be unique")
        lineage_ids.add(lineage["temporal_seed_id"])
        if not _is_nonzero_hash(lineage.get("lineage_root")):
            raise ValueError("Temporal seed lineage root must be non-zero")
    if len(lineage_ids) != len(seed_ids):
        raise ValueError("Temporal seed lineage must preserve every seed when present")


def _validate_temporal_web_inputs(
    web_summary: Dict[str, Any],
    web_refusals_payload: Dict[str, Any],
    seed_count: int,
) -> int:
    if not web_summary:
        raise ValueError("temporal_web_discovery_summary.json is missing")
    if web_summary.get("temporal_web_discovery_status") not in TEMPORAL_WEB_STATUSES:
        raise ValueError("temporal web discovery upstream status is invalid")
    if web_summary.get("temporal_seed_count") != seed_count:
        raise ValueError("temporal web discovery seed count must match temporal seeds")
    for counter_name in (
        "evidence_invented",
        "urls_invented",
        "quotes_created",
        "quotes_invented",
        "timestamps_created",
        "claims_created",
        "contradictions_created",
    ):
        if web_summary.get(counter_name) != 0:
            raise ValueError(f"temporal web discovery {counter_name} must remain 0")
    if web_summary.get("no_generated_outputs_committed") is not True:
        raise ValueError("temporal web discovery no_generated_outputs_committed must remain true")
    if not _closed_flags(web_summary):
        raise ValueError("temporal web discovery guardrails must remain closed")
    if not web_refusals_payload:
        raise ValueError("temporal_web_discovery_refusals.json is missing")
    web_refusals = web_refusals_payload.get("temporal_web_discovery_refusals")
    if not isinstance(web_refusals, list):
        raise ValueError("temporal web discovery refusals must be a list")
    if len(web_refusals) != web_summary.get("refusal_count"):
        raise ValueError("temporal web discovery refusal count does not match summary")
    return len(web_refusals)


def _registry_domains(source_registry: Dict[str, Any]) -> List[str]:
    if not source_registry:
        raise ValueError("source registry input is missing")
    if source_registry.get("registry_version") != SOURCE_REGISTRY_VERSION:
        raise ValueError("source registry version is invalid")
    registry_sources = source_registry.get("registry_sources")
    if not isinstance(registry_sources, list) or not registry_sources:
        raise ValueError("source registry must contain registry_sources")
    domains = set()
    for source in registry_sources:
        required = set(REGISTRY_SOURCE_FIELDS)
        optional = {"resolved_url", "verification_status", "source_origin", "verified_endpoints"}
        source_fields = set(source.keys())
        if not required <= source_fields or source_fields - required - optional:
            raise ValueError("source registry fields changed unexpectedly")
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
        if source.get("manual_review_required") is not True:
            raise ValueError("RegistrySource.manual_review_required must remain true")
        if not isinstance(source.get("trust_tier"), int):
            raise ValueError("RegistrySource.trust_tier must be an integer")
        for url_field in ("base_url", "resolved_url"):
            value = source.get(url_field, "")
            if isinstance(value, str) and _is_public_url(value):
                domains.add(_source_owner_from_url(value))
        verified_endpoints = source.get("verified_endpoints", [])
        if verified_endpoints is not None and not isinstance(verified_endpoints, list):
            raise ValueError("RegistrySource.verified_endpoints must be a list when present")
        for endpoint in verified_endpoints or []:
            for endpoint_field in ("base_url", "resolved_url"):
                value = endpoint.get(endpoint_field, "")
                if isinstance(value, str) and _is_public_url(value):
                    domains.add(_source_owner_from_url(value))
    return sorted(domains)


def _strategies_for_seed(seed: Dict[str, Any]) -> Tuple[Tuple[str, str], ...]:
    if seed["time_direction"] == "BEFORE":
        return BEFORE_STRATEGIES
    if seed["time_direction"] == "AFTER":
        return AFTER_STRATEGIES
    raise ValueError(f"Unsupported time_direction: {seed['time_direction']}")


def _fetch_url_text(url: str, timeout: int = 12) -> Tuple[int, str, str, str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; DumaBokoContradictionEngine/2.0; "
                "temporal-discovery-strategy-upgrade-only)"
            )
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            resolved_url = response.geturl()
            content_type = response.headers.get("content-type", "")
            body = ""
            if "text/html" in content_type or "application/xhtml" in content_type:
                body = response.read(800000).decode("utf-8", errors="replace")
            return status, resolved_url, content_type, body, ""
    except urllib.error.HTTPError as exc:
        content_type = exc.headers.get("content-type", "") if exc.headers else ""
        return int(exc.code), exc.geturl(), content_type, "", f"HTTP status {exc.code}"
    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
        http.client.HTTPException,
        OSError,
    ) as exc:
        return 0, url, "", "", f"Unable to fetch URL metadata: {exc}"


def _extract_title(page_text: str) -> str:
    title_patterns = (
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
        r"<title[^>]*>(.*?)</title>",
    )
    for pattern in title_patterns:
        match = re.search(pattern, page_text, re.IGNORECASE | re.DOTALL)
        if match:
            return _normalize_space(html.unescape(match.group(1)))
    return ""


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


def _duckduckgo_result_url(raw_href: str, search_url: str) -> str:
    href = html.unescape(raw_href)
    href = urljoin(search_url, href)
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        query = parse_qs(parsed.query)
        uddg = query.get("uddg", [""])[0]
        return unquote(uddg)
    return href


def _search_public_page(
    query: str,
    search_cache: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    if query in search_cache:
        return search_cache[query]
    search_url = _duckduckgo_url(query)
    status, resolved_url, content_type, page_text, error = _fetch_url_text(
        search_url, timeout=12
    )
    if error or status < 200 or status >= 400:
        result = {
            "search_url": search_url,
            "status": status,
            "resolved_url": resolved_url,
            "content_type": content_type,
            "title": "",
            "result_url": "",
            "refusal_code": "REFUSED_SEARCH_UNAVAILABLE",
            "refusal_reason": error or f"Search page returned HTTP status {status}.",
        }
        search_cache[query] = result
        return result
    if not content_type:
        result = {
            "search_url": search_url,
            "status": status,
            "resolved_url": resolved_url,
            "content_type": "",
            "title": "",
            "result_url": "",
            "refusal_code": "REFUSED_SEARCH_UNAVAILABLE",
            "refusal_reason": "Search page did not return a content type.",
        }
        search_cache[query] = result
        return result
    if not page_text:
        result = {
            "search_url": search_url,
            "status": status,
            "resolved_url": resolved_url,
            "content_type": content_type,
            "title": "",
            "result_url": "",
            "refusal_code": "REFUSED_SEARCH_UNAVAILABLE",
            "refusal_reason": f"Search page returned unsupported content-type: {content_type}",
        }
        search_cache[query] = result
        return result
    links = re.findall(
        r'<a[^>]+class=["\'][^"\']*result__a[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
        page_text,
        flags=re.IGNORECASE,
    )
    first_result_url = ""
    for raw_href in links:
        candidate_url = _duckduckgo_result_url(raw_href, resolved_url)
        if _is_public_url(candidate_url):
            first_result_url = candidate_url
            break
    result = {
        "search_url": resolved_url if _is_public_url(resolved_url) else search_url,
        "status": status,
        "resolved_url": resolved_url,
        "content_type": content_type,
        "title": _extract_title(page_text),
        "result_url": first_result_url,
        "refusal_code": "" if first_result_url else "REFUSED_NO_PUBLIC_RESULT",
        "refusal_reason": "" if first_result_url else "No public result URL was returned.",
    }
    search_cache[query] = result
    return result


def _verify_candidate_url(
    candidate_url: str,
    metadata_cache: Dict[str, Tuple[Optional[Dict[str, Any]], Optional[Tuple[str, str, int, str]]]],
) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[str, str, int, str]]]:
    if candidate_url in metadata_cache:
        return metadata_cache[candidate_url]
    if not _is_public_url(candidate_url):
        result = (
            None,
            ("REFUSED_METADATA_UNVERIFIED", "Candidate URL is not public HTTP(S).", 0, ""),
        )
        metadata_cache[candidate_url] = result
        return result
    status, resolved_url, content_type, page_text, error = _fetch_url_text(
        candidate_url, timeout=12
    )
    if error or status < 200 or status >= 400:
        result = (
            None,
            (
                "REFUSED_UNREACHABLE",
                error or f"Candidate URL returned HTTP status {status}.",
                status,
                content_type,
            ),
        )
        metadata_cache[candidate_url] = result
        return result
    if not content_type:
        result = (
            None,
            ("REFUSED_METADATA_UNVERIFIED", "Candidate URL did not return a content type.", status, ""),
        )
        metadata_cache[candidate_url] = result
        return result
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        result = (
            None,
            (
                "REFUSED_METADATA_UNVERIFIED",
                f"Candidate URL returned unsupported content-type for title metadata: {content_type}",
                status,
                content_type,
            ),
        )
        metadata_cache[candidate_url] = result
        return result
    if _is_login_required(resolved_url or candidate_url, page_text):
        result = (
            None,
            ("REFUSED_METADATA_UNVERIFIED", "Candidate URL appears to require login.", status, content_type),
        )
        metadata_cache[candidate_url] = result
        return result
    title = _extract_title(page_text)
    if not title:
        result = (
            None,
            (
                "REFUSED_METADATA_UNVERIFIED",
                "Candidate URL was reachable, but a non-empty page title could not be verified.",
                status,
                content_type,
            ),
        )
        metadata_cache[candidate_url] = result
        return result
    source_url = resolved_url if _is_public_url(resolved_url) else candidate_url
    metadata = {
        "candidate_url": source_url,
        "source_title": title,
        "source_owner": _source_owner_from_url(source_url),
        "http_status": status,
        "content_type": content_type,
        "is_search_result_page": _is_generic_search_url(source_url),
    }
    result = (metadata, None)
    metadata_cache[candidate_url] = result
    return result


def _make_candidate(
    sequence_number: int,
    seed: Dict[str, Any],
    strategy_name: str,
    query: str,
    candidate_url: str,
    source_title: str,
    source_owner: str,
    http_status: int,
    content_type: str,
    verification_status: str,
) -> Dict[str, Any]:
    candidate = {
        "temporal_strategy_candidate_id": f"TEMPORAL_STRATEGY_CANDIDATE_{sequence_number:06d}",
        "temporal_seed_id": seed["temporal_seed_id"],
        "normalized_claim_id": seed["normalized_claim_id"],
        "source_claim_id": seed["source_claim_id"],
        "time_direction": seed["time_direction"],
        "target_evidence_type": seed["target_evidence_type"],
        "strategy_name": strategy_name,
        "query": query,
        "candidate_url": candidate_url.strip(),
        "source_title": source_title.strip(),
        "source_owner": source_owner.strip().lower(),
        "http_status": int(http_status),
        "content_type": content_type.strip(),
        "verification_status": verification_status,
        "manual_review_required": True,
        "metadata_hash": "",
        "candidate_root": "",
    }
    candidate["metadata_hash"] = _hash_json(_candidate_metadata_material(candidate))
    candidate["candidate_root"] = _hash_json(_candidate_root_material(candidate))
    return candidate


def _make_refusal(
    sequence_number: int,
    seed: Dict[str, Any],
    strategy_name: str,
    query: str,
    candidate_url: str,
    code: str,
    reason: str,
    http_status: int = 0,
    content_type: str = "",
) -> Dict[str, Any]:
    refusal = {
        "temporal_strategy_refusal_id": f"TEMPORAL_STRATEGY_REFUSAL_{sequence_number:06d}",
        "temporal_seed_id": seed.get("temporal_seed_id", ""),
        "normalized_claim_id": seed.get("normalized_claim_id", ""),
        "source_claim_id": seed.get("source_claim_id", ""),
        "time_direction": seed.get("time_direction", ""),
        "target_evidence_type": seed.get("target_evidence_type", ""),
        "strategy_name": strategy_name,
        "query": query,
        "candidate_url": candidate_url or "",
        "seed_root": seed.get("seed_root", ""),
        "http_status": int(http_status),
        "content_type": content_type,
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


def _make_lineage(
    seed: Dict[str, Any],
    candidate: Optional[Dict[str, Any]],
    refusal: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    lineage = {
        "temporal_seed_id": seed["temporal_seed_id"],
        "normalized_claim_id": seed["normalized_claim_id"],
        "source_claim_id": seed["source_claim_id"],
        "seed_root": seed["seed_root"],
        "temporal_strategy_candidate_id": (
            candidate["temporal_strategy_candidate_id"] if candidate else ""
        ),
        "candidate_root": candidate["candidate_root"] if candidate else "",
        "temporal_strategy_refusal_id": refusal["temporal_strategy_refusal_id"] if refusal else "",
        "refusal_root": refusal["refusal_root"] if refusal else "",
        "lineage_root": "",
    }
    lineage["lineage_root"] = _hash_json(_lineage_root_material(lineage))
    return lineage


def validate_candidate(candidate: Dict[str, Any]) -> None:
    if set(candidate.keys()) != set(CANDIDATE_FIELDS):
        raise ValueError("Temporal strategy candidate fields changed unexpectedly")
    for field_name in (
        "temporal_strategy_candidate_id",
        "temporal_seed_id",
        "normalized_claim_id",
        "source_claim_id",
        "time_direction",
        "target_evidence_type",
        "strategy_name",
        "query",
        "candidate_url",
        "source_title",
        "source_owner",
        "content_type",
        "verification_status",
        "metadata_hash",
        "candidate_root",
    ):
        _require_nonempty_string(candidate, field_name, "TemporalStrategyCandidate")
    if candidate["time_direction"] not in TIME_DIRECTIONS:
        raise ValueError("TemporalStrategyCandidate.time_direction unsupported")
    if candidate["target_evidence_type"] not in TARGET_EVIDENCE_TYPES:
        raise ValueError("TemporalStrategyCandidate.target_evidence_type unsupported")
    if candidate["verification_status"] not in VERIFICATION_STATUSES:
        raise ValueError("TemporalStrategyCandidate.verification_status unsupported")
    if candidate["verification_status"].startswith("REFUSED_"):
        raise ValueError("TemporalStrategyCandidate must not carry refusal status")
    if not _is_public_url(candidate["candidate_url"]):
        raise ValueError("TemporalStrategyCandidate.candidate_url must be public HTTP(S)")
    if candidate["manual_review_required"] is not True:
        raise ValueError("TemporalStrategyCandidate.manual_review_required must remain true")
    if not isinstance(candidate["http_status"], int):
        raise ValueError("TemporalStrategyCandidate.http_status must be an integer")
    if candidate["verification_status"] == "VERIFIED_REACHABLE_TEMPORAL_ENDPOINT":
        if _is_generic_search_url(candidate["candidate_url"]):
            raise ValueError("Verified temporal endpoint must not be a search-result page")
        if candidate["http_status"] < 200 or candidate["http_status"] >= 400:
            raise ValueError("Verified temporal endpoint http_status must be 200-399")
        if not candidate["content_type"].strip():
            raise ValueError("Verified temporal endpoint content_type must be non-empty")
    if candidate["verification_status"] == "DISCOVERED_REQUIRES_MANUAL_REVIEW":
        if candidate["http_status"] < 200 or candidate["http_status"] >= 400:
            raise ValueError("Manual-review temporal strategy candidate must be reachable")
    if candidate["metadata_hash"] != _hash_json(_candidate_metadata_material(candidate)):
        raise ValueError(f"metadata_hash mismatch for {candidate['temporal_strategy_candidate_id']}")
    if candidate["candidate_root"] != _hash_json(_candidate_root_material(candidate)):
        raise ValueError(f"candidate_root mismatch for {candidate['temporal_strategy_candidate_id']}")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Temporal strategy refusal fields changed unexpectedly")
    for field_name in (
        "temporal_strategy_refusal_id",
        "temporal_seed_id",
        "normalized_claim_id",
        "source_claim_id",
        "time_direction",
        "target_evidence_type",
        "strategy_name",
        "query",
        "candidate_url",
        "seed_root",
        "refusal_code",
        "refusal_reason",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "TemporalStrategyRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError("TemporalStrategyRefusal.refusal_code unsupported")
    if not _is_nonzero_hash(refusal["seed_root"]):
        raise ValueError("TemporalStrategyRefusal.seed_root must be preserved")
    if refusal["manual_review_required"] is not True:
        raise ValueError("TemporalStrategyRefusal.manual_review_required must remain true")
    if not _closed_flags(refusal):
        raise ValueError("TemporalStrategyRefusal guardrails must remain closed")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['temporal_strategy_refusal_id']}")


def validate_lineage(lineage: Dict[str, Any]) -> None:
    if set(lineage.keys()) != set(LINEAGE_FIELDS):
        raise ValueError("Temporal strategy lineage fields changed unexpectedly")
    for field_name in (
        "temporal_seed_id",
        "normalized_claim_id",
        "source_claim_id",
        "seed_root",
        "lineage_root",
    ):
        _require_nonempty_string(lineage, field_name, "TemporalStrategyLineage")
    if not _is_nonzero_hash(lineage["seed_root"]):
        raise ValueError("TemporalStrategyLineage.seed_root must be preserved")
    if not lineage["candidate_root"] and not lineage["refusal_root"]:
        raise ValueError("TemporalStrategyLineage must preserve candidate or refusal root")
    if lineage["candidate_root"] and lineage["refusal_root"]:
        raise ValueError("TemporalStrategyLineage cannot preserve both candidate and refusal root")
    if lineage["lineage_root"] != _hash_json(_lineage_root_material(lineage)):
        raise ValueError(f"lineage_root mismatch for {lineage['temporal_seed_id']}")


def _dry_run_candidate(
    sequence_number: int,
    seed: Dict[str, Any],
    strategy_name: str,
    query: str,
) -> Dict[str, Any]:
    candidate_url = _duckduckgo_url(query)
    return _make_candidate(
        sequence_number,
        seed,
        strategy_name,
        query,
        candidate_url,
        "TEMPORAL_STRATEGY_DEMO_UNVERIFIED",
        _source_owner_from_url(candidate_url),
        0,
        "UNVERIFIED_PENDING_DRY_RUN",
        "TEMPORAL_STRATEGY_DEMO_UNVERIFIED",
    )


def _search_page_candidate(
    sequence_number: int,
    seed: Dict[str, Any],
    strategy_name: str,
    query: str,
    search_result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    search_url = search_result.get("search_url", _duckduckgo_url(query))
    status = int(search_result.get("status") or 0)
    content_type = str(search_result.get("content_type") or "")
    title = str(search_result.get("title") or "")
    if not _is_public_url(search_url) or status < 200 or status >= 400 or not content_type or not title:
        return None
    return _make_candidate(
        sequence_number,
        seed,
        strategy_name,
        query,
        search_url,
        title,
        _source_owner_from_url(search_url),
        status,
        content_type,
        "DISCOVERED_REQUIRES_MANUAL_REVIEW",
    )


def _probe_single_strategy(
    seed: Dict[str, Any],
    strategy_name: str,
    query: str,
    mode: str,
    candidate_sequence: int,
    refusal_sequence: int,
    search_cache: Dict[str, Dict[str, Any]],
    metadata_cache: Dict[str, Tuple[Optional[Dict[str, Any]], Optional[Tuple[str, str, int, str]]]],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    search_url = _duckduckgo_url(query)
    if mode == "dry-run":
        return _dry_run_candidate(candidate_sequence, seed, strategy_name, query), None

    search_result = _search_public_page(query, search_cache)
    if search_result.get("refusal_code") == "REFUSED_SEARCH_UNAVAILABLE":
        return None, _make_refusal(
            refusal_sequence,
            seed,
            strategy_name,
            query,
            search_url,
            "REFUSED_SEARCH_UNAVAILABLE",
            str(search_result.get("refusal_reason") or "Search page was unavailable."),
            http_status=int(search_result.get("status") or 0),
            content_type=str(search_result.get("content_type") or ""),
        )

    result_url = str(search_result.get("result_url") or "")
    if not result_url:
        candidate = _search_page_candidate(
            candidate_sequence,
            seed,
            strategy_name,
            query,
            search_result,
        )
        if candidate is not None:
            return candidate, None
        return None, _make_refusal(
            refusal_sequence,
            seed,
            strategy_name,
            query,
            search_url,
            "REFUSED_NO_PUBLIC_RESULT",
            str(search_result.get("refusal_reason") or "No public result URL was returned."),
            http_status=int(search_result.get("status") or 0),
            content_type=str(search_result.get("content_type") or ""),
        )

    metadata, metadata_refusal = _verify_candidate_url(result_url, metadata_cache)
    if metadata_refusal is not None:
        code, reason, http_status, content_type = metadata_refusal
        if _is_generic_search_url(result_url):
            candidate = _search_page_candidate(
                candidate_sequence,
                seed,
                strategy_name,
                query,
                search_result,
            )
            if candidate is not None:
                return candidate, None
        return None, _make_refusal(
            refusal_sequence,
            seed,
            strategy_name,
            query,
            result_url,
            code,
            reason,
            http_status=http_status,
            content_type=content_type,
        )
    if metadata is None:
        return None, _make_refusal(
            refusal_sequence,
            seed,
            strategy_name,
            query,
            result_url,
            "REFUSED_METADATA_UNVERIFIED",
            "Candidate metadata resolver returned no metadata.",
        )
    verification_status = (
        "DISCOVERED_REQUIRES_MANUAL_REVIEW"
        if metadata["is_search_result_page"]
        else "VERIFIED_REACHABLE_TEMPORAL_ENDPOINT"
    )
    return _make_candidate(
        candidate_sequence,
        seed,
        strategy_name,
        query,
        metadata["candidate_url"],
        metadata["source_title"],
        metadata["source_owner"],
        metadata["http_status"],
        metadata["content_type"],
        verification_status,
    ), None


def _build_candidates_and_refusals(
    seeds: List[Dict[str, Any]],
    mode: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    candidates: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    lineage_records: List[Dict[str, Any]] = []
    search_cache: Dict[str, Dict[str, Any]] = {}
    metadata_cache: Dict[
        str, Tuple[Optional[Dict[str, Any]], Optional[Tuple[str, str, int, str]]]
    ] = {}
    for seed in seeds:
        validate_temporal_seed(seed)
        for strategy_name, query in _strategies_for_seed(seed):
            candidate, refusal = _probe_single_strategy(
                seed,
                strategy_name,
                query,
                mode,
                len(candidates) + 1,
                len(refusals) + 1,
                search_cache,
                metadata_cache,
            )
            if candidate is not None:
                validate_candidate(candidate)
                lineage = _make_lineage(seed, candidate, None)
                validate_lineage(lineage)
                candidates.append(candidate)
                lineage_records.append(lineage)
            if refusal is not None:
                validate_refusal(refusal)
                lineage = _make_lineage(seed, None, refusal)
                validate_lineage(lineage)
                refusals.append(refusal)
                lineage_records.append(lineage)
    return candidates, refusals, lineage_records


def _status_for(candidate_count: int, refusal_count: int) -> str:
    if candidate_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if candidate_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _build_report(
    status: str,
    mode: str,
    seed_count: int,
    candidates: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    candidate_lines = ["- None"]
    if candidates:
        candidate_lines = []
        for candidate in candidates[:20]:
            candidate_lines.extend(
                [
                    f"- {candidate['temporal_strategy_candidate_id']}",
                    f"  - Seed: {candidate['temporal_seed_id']}",
                    f"  - Strategy: {candidate['strategy_name']}",
                    f"  - URL: {candidate['candidate_url']}",
                    f"  - Verification Status: {candidate['verification_status']}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['temporal_strategy_refusal_id']}: {refusal['refusal_code']}",
                    f"  - Seed: {refusal['temporal_seed_id']}",
                    f"  - Strategy: {refusal['strategy_name']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Temporal Discovery Strategy Upgrade v2",
            "",
            "This lane emits targeted temporal discovery strategy candidates and "
            "refusals only. It does not invent URLs, create quotes, timestamps, "
            "claims, contradictions, production readiness, or approved evidence.",
            "",
            "## Summary",
            f"- temporal_strategy_status: {status}",
            f"- mode: {mode}",
            f"- temporal_seed_count: {seed_count}",
            f"- strategy_candidate_count: {len(candidates)}",
            f"- verified_temporal_endpoint_count: {sum(1 for c in candidates if c['verification_status'] == 'VERIFIED_REACHABLE_TEMPORAL_ENDPOINT')}",
            f"- manual_review_required_count: {sum(1 for c in candidates if c['manual_review_required'] is True)}",
            f"- refusal_count: {len(refusals)}",
            f"- temporal_strategy_root: {root}",
            "",
            "## First Strategy Candidates",
            *candidate_lines,
            "",
            "## First Strategy Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- URLs Invented: 0",
            "- Quotes Created: 0",
            "- Timestamps Created: 0",
            "- Claims Created: 0",
            "- Contradictions Created: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "",
        ]
    )


def build_temporal_discovery_strategy_upgrade(
    mode: str = "dry-run",
    temporal_seeds_path: Path = DEFAULT_TEMPORAL_SEEDS,
    temporal_web_summary_path: Path = DEFAULT_TEMPORAL_WEB_SUMMARY,
    temporal_web_refusals_path: Path = DEFAULT_TEMPORAL_WEB_REFUSALS,
    source_registry_path: Path = DEFAULT_SOURCE_REGISTRY,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "probe-web"):
        raise ValueError("mode must be dry-run or probe-web")

    temporal_payload = _load_json(temporal_seeds_path)
    temporal_web_summary = _load_json(temporal_web_summary_path)
    temporal_web_refusals = _load_json(temporal_web_refusals_path)
    source_registry = _load_json(source_registry_path)

    seeds, seed_lineage = _load_temporal_seeds(temporal_payload)
    schema = _schema()
    validate_schema(schema)
    for seed in seeds:
        validate_temporal_seed(seed)
    _validate_seed_lineage(seeds, seed_lineage)
    temporal_web_refusal_count = _validate_temporal_web_inputs(
        temporal_web_summary,
        temporal_web_refusals,
        len(seeds),
    )
    registry_domains = _registry_domains(source_registry)

    candidates, refusals, lineage_records = _build_candidates_and_refusals(seeds, mode)
    candidate_roots = [candidate["candidate_root"] for candidate in candidates]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    lineage_roots = [lineage["lineage_root"] for lineage in lineage_records]
    verified_count = sum(
        1
        for candidate in candidates
        if candidate["verification_status"] == "VERIFIED_REACHABLE_TEMPORAL_ENDPOINT"
    )
    manual_review_required_count = sum(
        1 for candidate in candidates if candidate["manual_review_required"] is True
    )
    search_result_review_count = sum(
        1
        for candidate in candidates
        if candidate["verification_status"] == "DISCOVERED_REQUIRES_MANUAL_REVIEW"
        and _is_generic_search_url(candidate["candidate_url"])
    )
    before_probe_count = sum(1 for candidate in candidates if candidate["time_direction"] == "BEFORE")
    after_probe_count = sum(1 for candidate in candidates if candidate["time_direction"] == "AFTER")
    root = _hash_json(
        {
            "candidate_roots": sorted(candidate_roots),
            "refusal_roots": sorted(refusal_roots),
            "lineage_roots": sorted(lineage_roots),
            "evidence_invented": 0,
            "urls_invented": 0,
            "quotes_created": 0,
            "quotes_invented": 0,
            "timestamps_created": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        }
    )
    status = _status_for(len(candidates), len(refusals))
    report = _build_report(status, mode, len(seeds), candidates, refusals, root)
    summary = {
        "temporal_strategy_status": status,
        "mode": mode,
        "temporal_seed_count": len(seeds),
        "temporal_web_refusal_count": temporal_web_refusal_count,
        "source_registry_count": len(source_registry.get("registry_sources", [])),
        "registry_domain_count": len(registry_domains),
        "registry_domains": registry_domains,
        "unique_strategy_query_count": len(
            {query for seed in seeds for _, query in _strategies_for_seed(seed)}
        ),
        "strategy_candidate_count": len(candidates),
        "verified_temporal_endpoint_count": verified_count,
        "manual_review_required_count": manual_review_required_count,
        "search_result_review_count": search_result_review_count,
        "before_probe_count": before_probe_count,
        "after_probe_count": after_probe_count,
        "refusal_count": len(refusals),
        "lineage_preserved_count": len(lineage_records),
        "candidate_roots": candidate_roots,
        "refusal_roots": refusal_roots,
        "lineage_roots": lineage_roots,
        "temporal_strategy_schema_hash": _hash_json(schema),
        "temporal_strategy_report_hash": _sha256_text(report),
        "temporal_strategy_root": root,
        "evidence_invented": 0,
        "urls_invented": 0,
        "quotes_created": 0,
        "quotes_invented": 0,
        "timestamps_created": 0,
        "claims_created": 0,
        "contradictions_created": 0,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    for counter_name in (
        "evidence_invented",
        "urls_invented",
        "quotes_created",
        "quotes_invented",
        "timestamps_created",
        "claims_created",
        "contradictions_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0")
    if not _closed_flags(summary):
        raise ValueError("temporal strategy guardrails must remain closed")

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(
        CANDIDATES_OUTPUT,
        {
            "temporal_strategy_candidates": candidates,
            "temporal_strategy_lineage": lineage_records,
        },
    )
    _write_json(REFUSALS_OUTPUT, {"temporal_strategy_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "summary": summary,
        "temporal_strategy_candidates": candidates,
        "temporal_strategy_refusals": refusals,
        "temporal_strategy_lineage": lineage_records,
        "schema": schema,
        "report": report,
    }
