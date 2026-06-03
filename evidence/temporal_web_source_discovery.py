#!/usr/bin/env python3
"""
Temporal Web Source Discovery v2.

Converts temporal evidence expansion seeds into public source candidates, or
deterministic refusals, using public search result metadata only. This lane does
not invent URLs, create quotes, timestamps, claims, contradictions, evidence
approvals, production readiness, or approved evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse
import hashlib
import html
import json
import re
import urllib.error
import urllib.request


DEFAULT_TEMPORAL_SEEDS = Path(
    "outputs/temporal_evidence_expansion_seeds/temporal_expansion_seeds.json"
)
DEFAULT_TEMPORAL_SUMMARY = Path(
    "outputs/temporal_evidence_expansion_seeds/temporal_expansion_summary.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/temporal_web_source_discovery")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_web_discovery_summary.json"
SOURCES_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_discovered_sources.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_web_discovery_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_web_discovery_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_web_discovery_schema.json"

SCHEMA_VERSION = "temporal_web_source_discovery_v2"

DRY_RUN_STATUS = "TEMPORAL_WEB_SOURCE_DISCOVERY_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "TEMPORAL_WEB_SOURCE_DISCOVERY_CANDIDATE"
PARTIAL_STATUS = "TEMPORAL_WEB_SOURCE_DISCOVERY_PARTIAL"
REFUSED_STATUS = "TEMPORAL_WEB_SOURCE_DISCOVERY_REFUSED"

UPSTREAM_TEMPORAL_STATUSES = (
    "TEMPORAL_EVIDENCE_EXPANSION_SEEDS_CANDIDATE",
    "TEMPORAL_EVIDENCE_EXPANSION_SEEDS_PARTIAL",
)

VERIFICATION_STATUS = "TEMPORAL_SOURCE_REQUIRES_MANUAL_REVIEW"
DISCOVERY_METHOD = "duckduckgo_html_public_search_metadata_lookup"

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

LINEAGE_FIELDS = (
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

DISCOVERED_SOURCE_FIELDS = (
    "temporal_discovered_source_id",
    "temporal_seed_id",
    "normalized_claim_id",
    "source_claim_id",
    "time_direction",
    "target_evidence_type",
    "search_query",
    "source_url",
    "source_title",
    "source_owner",
    "discovery_method",
    "http_status",
    "content_type",
    "verification_status",
    "manual_review_required",
    "metadata_hash",
    "source_root",
)

DISCOVERY_LINEAGE_FIELDS = (
    "temporal_seed_id",
    "normalized_claim_id",
    "source_claim_id",
    "seed_root",
    "source_root",
    "refusal_root",
    "lineage_root",
)

REFUSAL_FIELDS = (
    "refusal_id",
    "temporal_seed_id",
    "normalized_claim_id",
    "source_claim_id",
    "time_direction",
    "target_evidence_type",
    "search_query",
    "seed_root",
    "refusal_code",
    "refusal_reason",
    "http_status",
    "content_type",
    "manual_review_required",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "refusal_root",
)

REFUSAL_CODES = (
    "REFUSED_NO_PUBLIC_RESULT",
    "REFUSED_SEARCH_UNAVAILABLE",
    "REFUSED_SOURCE_UNREACHABLE",
    "REFUSED_METADATA_UNVERIFIED",
    "REFUSED_UNSUPPORTED_SOURCE",
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


def _source_metadata_material(source: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field_name: source[field_name]
        for field_name in DISCOVERED_SOURCE_FIELDS
        if field_name not in ("metadata_hash", "source_root")
    }


def _source_root_material(source: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(source)
    material.pop("source_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _discovery_lineage_root_material(lineage: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(lineage)
    material.pop("lineage_root", None)
    return material


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "temporal_web_source_discovery_only": True,
        "modes": ["dry-run", "discover-web"],
        "upstream_temporal_statuses": list(UPSTREAM_TEMPORAL_STATUSES),
        "time_direction_values": list(TIME_DIRECTIONS),
        "target_evidence_types": list(TARGET_EVIDENCE_TYPES),
        "temporal_seed_fields": list(TEMPORAL_SEED_FIELDS),
        "discovered_source_fields": list(DISCOVERED_SOURCE_FIELDS),
        "discovery_lineage_fields": list(DISCOVERY_LINEAGE_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "verification_status": VERIFICATION_STATUS,
        "discovery_method": DISCOVERY_METHOD,
        "discovery_policy": (
            "Discover-web uses the first public DuckDuckGo HTML result for each "
            "temporal seed query, then verifies reachable HTTP metadata. It must "
            "not infer or invent URLs when no result is returned."
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
            "metadata_hash": "sha256 over discovered source metadata excluding roots",
            "source_root": "sha256 over discovered source excluding source_root",
            "refusal_root": "sha256 over refusal excluding refusal_root",
            "lineage_root": "sha256 over source/refusal seed lineage excluding lineage_root",
            "temporal_web_discovery_root": (
                "sha256 over sorted source roots, refusal roots, lineage roots, "
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
        raise ValueError("temporal web discovery schema_version changed unexpectedly")
    if schema.get("discovered_source_fields") != list(DISCOVERED_SOURCE_FIELDS):
        raise ValueError("temporal discovered source fields changed unexpectedly")
    if schema.get("refusal_fields") != list(REFUSAL_FIELDS):
        raise ValueError("temporal web refusal fields changed unexpectedly")
    if schema.get("refusal_codes") != list(REFUSAL_CODES):
        raise ValueError("temporal web refusal codes changed unexpectedly")


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


def _validate_upstream_summary(summary: Dict[str, Any], seeds: List[Dict[str, Any]]) -> None:
    if not summary:
        raise ValueError("temporal_expansion_summary.json is missing")
    if summary.get("temporal_expansion_status") not in UPSTREAM_TEMPORAL_STATUSES:
        raise ValueError("temporal expansion upstream status is invalid")
    if summary.get("temporal_seed_count") != len(seeds):
        raise ValueError("temporal seed count does not match summary")
    if summary.get("before_seed_count", 0) + summary.get("after_seed_count", 0) != len(seeds):
        raise ValueError("before/after temporal seed counts must sum to seed count")
    for counter_name in (
        "evidence_invented",
        "urls_invented",
        "quotes_created",
        "quotes_invented",
        "contradictions_created",
        "proof_chains_created",
        "final_reports_created",
        "word_reports_created",
    ):
        if summary.get(counter_name) != 0:
            raise ValueError(f"upstream {counter_name} must remain 0")
    if summary.get("no_generated_outputs_committed") is not True:
        raise ValueError("upstream no_generated_outputs_committed must remain true")
    if not _closed_flags(summary):
        raise ValueError("temporal expansion guardrails must remain closed")


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
        if set(lineage.keys()) != set(LINEAGE_FIELDS):
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


def _fetch_url_text(url: str, timeout: int = 12) -> Tuple[int, str, str, str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; DumaBokoContradictionEngine/2.0; "
                "temporal-web-source-discovery-only)"
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
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
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
    seed: Dict[str, Any],
    search_cache: Dict[str, Tuple[Optional[str], Optional[str], Optional[str]]],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    query = seed["search_query"]
    if query in search_cache:
        return search_cache[query]
    search_url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    status, resolved_url, content_type, page_text, error = _fetch_url_text(
        search_url, timeout=12
    )
    if error or status < 200 or status >= 400:
        result = (
            None,
            "REFUSED_SEARCH_UNAVAILABLE",
            error or f"Search page returned HTTP status {status}.",
        )
        search_cache[query] = result
        return result
    if not content_type:
        result = (
            None,
            "REFUSED_SEARCH_UNAVAILABLE",
            "Search page did not return a content type.",
        )
        search_cache[query] = result
        return result
    if not page_text:
        result = (
            None,
            "REFUSED_SEARCH_UNAVAILABLE",
            f"Search page returned unsupported content-type: {content_type}",
        )
        search_cache[query] = result
        return result
    links = re.findall(
        r'<a[^>]+class=["\'][^"\']*result__a[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
        page_text,
        flags=re.IGNORECASE,
    )
    for raw_href in links:
        candidate_url = _duckduckgo_result_url(raw_href, resolved_url)
        if not _is_public_url(candidate_url):
            continue
        if _is_generic_search_url(candidate_url):
            continue
        result = (candidate_url, None, None)
        search_cache[query] = result
        return result
    result = (None, "REFUSED_NO_PUBLIC_RESULT", "No public result URL was returned.")
    search_cache[query] = result
    return result


def _source_from_metadata(
    seed: Dict[str, Any],
    source_sequence: int,
    source_url: str,
    source_title: str,
    source_owner: str,
    http_status: int,
    content_type: str,
) -> Dict[str, Any]:
    source = {
        "temporal_discovered_source_id": f"TEMPORAL_DISCOVERED_SOURCE_{source_sequence:06d}",
        "temporal_seed_id": seed["temporal_seed_id"],
        "normalized_claim_id": seed["normalized_claim_id"],
        "source_claim_id": seed["source_claim_id"],
        "time_direction": seed["time_direction"],
        "target_evidence_type": seed["target_evidence_type"],
        "search_query": seed["search_query"],
        "source_url": source_url.strip(),
        "source_title": source_title.strip(),
        "source_owner": source_owner.strip().lower(),
        "discovery_method": DISCOVERY_METHOD,
        "http_status": int(http_status),
        "content_type": content_type.strip(),
        "verification_status": VERIFICATION_STATUS,
        "manual_review_required": True,
        "metadata_hash": "",
        "source_root": "",
    }
    source["metadata_hash"] = _hash_json(_source_metadata_material(source))
    source["source_root"] = _hash_json(_source_root_material(source))
    return source


def _make_refusal(
    seed: Dict[str, Any],
    refusal_sequence: int,
    code: str,
    reason: str,
    http_status: int = 0,
    content_type: str = "",
) -> Dict[str, Any]:
    refusal = {
        "refusal_id": f"TEMPORAL_WEB_DISCOVERY_REFUSAL_{refusal_sequence:06d}",
        "temporal_seed_id": seed.get("temporal_seed_id", ""),
        "normalized_claim_id": seed.get("normalized_claim_id", ""),
        "source_claim_id": seed.get("source_claim_id", ""),
        "time_direction": seed.get("time_direction", ""),
        "target_evidence_type": seed.get("target_evidence_type", ""),
        "search_query": seed.get("search_query", ""),
        "seed_root": seed.get("seed_root", ""),
        "refusal_code": code,
        "refusal_reason": reason,
        "http_status": int(http_status),
        "content_type": content_type,
        "manual_review_required": True,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def _verify_source_url(
    source_url: str,
    metadata_cache: Dict[str, Tuple[Optional[Dict[str, Any]], Optional[Tuple[str, str, int, str]]]],
) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[str, str, int, str]]]:
    if source_url in metadata_cache:
        return metadata_cache[source_url]
    if not _is_public_url(source_url):
        result = (
            None,
            ("REFUSED_UNSUPPORTED_SOURCE", "Result URL is not public HTTP(S).", 0, ""),
        )
        metadata_cache[source_url] = result
        return result
    if _is_generic_search_url(source_url):
        result = (
            None,
            ("REFUSED_UNSUPPORTED_SOURCE", "Result URL is a generic search page.", 0, ""),
        )
        metadata_cache[source_url] = result
        return result
    status, resolved_url, content_type, page_text, error = _fetch_url_text(
        source_url, timeout=12
    )
    if error or status < 200 or status >= 400:
        result = (
            None,
            (
                "REFUSED_SOURCE_UNREACHABLE",
                error or f"Source URL returned HTTP status {status}.",
                status,
                content_type,
            ),
        )
        metadata_cache[source_url] = result
        return result
    if not content_type:
        result = (
            None,
            ("REFUSED_METADATA_UNVERIFIED", "Source URL did not return a content type.", status, ""),
        )
        metadata_cache[source_url] = result
        return result
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        result = (
            None,
            (
                "REFUSED_UNSUPPORTED_SOURCE",
                f"Unsupported source content-type for title metadata: {content_type}",
                status,
                content_type,
            ),
        )
        metadata_cache[source_url] = result
        return result
    if _is_generic_search_url(resolved_url):
        result = (
            None,
            ("REFUSED_UNSUPPORTED_SOURCE", "Resolved URL is a generic search page.", status, content_type),
        )
        metadata_cache[source_url] = result
        return result
    title = _extract_title(page_text)
    if not title:
        result = (
            None,
            (
                "REFUSED_METADATA_UNVERIFIED",
                "Source was reachable, but a non-empty page title could not be verified.",
                status,
                content_type,
            ),
        )
        metadata_cache[source_url] = result
        return result
    metadata = {
        "source_url": resolved_url,
        "source_title": title,
        "source_owner": _source_owner_from_url(resolved_url),
        "http_status": status,
        "content_type": content_type,
    }
    result = (metadata, None)
    metadata_cache[source_url] = result
    return result


def validate_discovered_source(source: Dict[str, Any]) -> None:
    if set(source.keys()) != set(DISCOVERED_SOURCE_FIELDS):
        raise ValueError("Temporal discovered source fields changed unexpectedly")
    for field_name in (
        "temporal_discovered_source_id",
        "temporal_seed_id",
        "normalized_claim_id",
        "source_claim_id",
        "time_direction",
        "target_evidence_type",
        "search_query",
        "source_url",
        "source_title",
        "source_owner",
        "discovery_method",
        "content_type",
        "verification_status",
        "metadata_hash",
        "source_root",
    ):
        _require_nonempty_string(source, field_name, "TemporalDiscoveredSource")
    if source["time_direction"] not in TIME_DIRECTIONS:
        raise ValueError("TemporalDiscoveredSource.time_direction changed unexpectedly")
    if source["target_evidence_type"] not in TARGET_EVIDENCE_TYPES:
        raise ValueError("TemporalDiscoveredSource target_evidence_type unsupported")
    if not _is_public_url(source["source_url"]):
        raise ValueError("TemporalDiscoveredSource.source_url must be public HTTP(S)")
    if _is_generic_search_url(source["source_url"]):
        raise ValueError("TemporalDiscoveredSource.source_url must not be a search page")
    if not isinstance(source["http_status"], int) or source["http_status"] < 200 or source["http_status"] >= 400:
        raise ValueError("TemporalDiscoveredSource.http_status must be 200-399")
    if source["discovery_method"] != DISCOVERY_METHOD:
        raise ValueError("TemporalDiscoveredSource.discovery_method changed unexpectedly")
    if source["verification_status"] != VERIFICATION_STATUS:
        raise ValueError("TemporalDiscoveredSource.verification_status changed unexpectedly")
    if source["manual_review_required"] is not True:
        raise ValueError("TemporalDiscoveredSource.manual_review_required must remain true")
    if source["metadata_hash"] != _hash_json(_source_metadata_material(source)):
        raise ValueError(f"metadata_hash mismatch for {source['temporal_discovered_source_id']}")
    if source["source_root"] != _hash_json(_source_root_material(source)):
        raise ValueError(f"source_root mismatch for {source['temporal_discovered_source_id']}")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Temporal web refusal fields changed unexpectedly")
    for field_name in (
        "refusal_id",
        "temporal_seed_id",
        "normalized_claim_id",
        "source_claim_id",
        "time_direction",
        "target_evidence_type",
        "search_query",
        "seed_root",
        "refusal_code",
        "refusal_reason",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "TemporalWebDiscoveryRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}")
    if not _is_nonzero_hash(refusal["seed_root"]):
        raise ValueError("TemporalWebDiscoveryRefusal.seed_root must be preserved")
    if refusal["manual_review_required"] is not True:
        raise ValueError("TemporalWebDiscoveryRefusal.manual_review_required must remain true")
    if not _closed_flags(refusal):
        raise ValueError("TemporalWebDiscoveryRefusal guardrails must remain closed")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}")


def _make_lineage(
    seed: Dict[str, Any],
    source: Optional[Dict[str, Any]],
    refusal: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    lineage = {
        "temporal_seed_id": seed["temporal_seed_id"],
        "normalized_claim_id": seed["normalized_claim_id"],
        "source_claim_id": seed["source_claim_id"],
        "seed_root": seed["seed_root"],
        "source_root": source["source_root"] if source else "",
        "refusal_root": refusal["refusal_root"] if refusal else "",
        "lineage_root": "",
    }
    lineage["lineage_root"] = _hash_json(_discovery_lineage_root_material(lineage))
    return lineage


def validate_discovery_lineage(lineage: Dict[str, Any]) -> None:
    if set(lineage.keys()) != set(DISCOVERY_LINEAGE_FIELDS):
        raise ValueError("Temporal discovery lineage fields changed unexpectedly")
    for field_name in (
        "temporal_seed_id",
        "normalized_claim_id",
        "source_claim_id",
        "seed_root",
        "lineage_root",
    ):
        _require_nonempty_string(lineage, field_name, "TemporalDiscoveryLineage")
    if not _is_nonzero_hash(lineage["seed_root"]):
        raise ValueError("TemporalDiscoveryLineage.seed_root must be preserved")
    if not lineage["source_root"] and not lineage["refusal_root"]:
        raise ValueError("TemporalDiscoveryLineage must preserve source or refusal root")
    if lineage["source_root"] and lineage["refusal_root"]:
        raise ValueError("TemporalDiscoveryLineage cannot preserve both source and refusal root")
    if lineage["lineage_root"] != _hash_json(_discovery_lineage_root_material(lineage)):
        raise ValueError(f"lineage_root mismatch for {lineage['temporal_seed_id']}")


def _discover_sources(
    seeds: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    sources: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    discovery_lineage: List[Dict[str, Any]] = []
    search_cache: Dict[str, Tuple[Optional[str], Optional[str], Optional[str]]] = {}
    metadata_cache: Dict[
        str, Tuple[Optional[Dict[str, Any]], Optional[Tuple[str, str, int, str]]]
    ] = {}
    source_sequence = 1
    refusal_sequence = 1
    for seed in seeds:
        try:
            validate_temporal_seed(seed)
        except ValueError as exc:
            refusal = _make_refusal(
                seed,
                refusal_sequence,
                "REFUSED_METADATA_UNVERIFIED",
                f"Temporal seed validation failed: {exc}",
            )
            validate_refusal(refusal)
            lineage = _make_lineage(seed, None, refusal)
            validate_discovery_lineage(lineage)
            refusals.append(refusal)
            discovery_lineage.append(lineage)
            refusal_sequence += 1
            continue

        result_url, refusal_code, refusal_reason = _search_public_page(seed, search_cache)
        if result_url is None:
            refusal = _make_refusal(
                seed,
                refusal_sequence,
                refusal_code or "REFUSED_NO_PUBLIC_RESULT",
                refusal_reason or "No public source result was found.",
            )
            validate_refusal(refusal)
            lineage = _make_lineage(seed, None, refusal)
            validate_discovery_lineage(lineage)
            refusals.append(refusal)
            discovery_lineage.append(lineage)
            refusal_sequence += 1
            continue

        metadata, metadata_refusal = _verify_source_url(result_url, metadata_cache)
        if metadata_refusal is not None:
            code, reason, http_status, content_type = metadata_refusal
            refusal = _make_refusal(
                seed,
                refusal_sequence,
                code,
                reason,
                http_status=http_status,
                content_type=content_type,
            )
            validate_refusal(refusal)
            lineage = _make_lineage(seed, None, refusal)
            validate_discovery_lineage(lineage)
            refusals.append(refusal)
            discovery_lineage.append(lineage)
            refusal_sequence += 1
            continue

        if metadata is None:
            refusal = _make_refusal(
                seed,
                refusal_sequence,
                "REFUSED_METADATA_UNVERIFIED",
                "Source metadata resolver returned no metadata.",
            )
            validate_refusal(refusal)
            lineage = _make_lineage(seed, None, refusal)
            validate_discovery_lineage(lineage)
            refusals.append(refusal)
            discovery_lineage.append(lineage)
            refusal_sequence += 1
            continue

        source = _source_from_metadata(
            seed,
            source_sequence,
            metadata["source_url"],
            metadata["source_title"],
            metadata["source_owner"],
            metadata["http_status"],
            metadata["content_type"],
        )
        validate_discovered_source(source)
        lineage = _make_lineage(seed, source, None)
        validate_discovery_lineage(lineage)
        sources.append(source)
        discovery_lineage.append(lineage)
        source_sequence += 1
    return sources, refusals, discovery_lineage


def _status_for(mode: str, discovered_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if discovered_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if discovered_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _build_report(
    status: str,
    mode: str,
    seed_count: int,
    sources: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    source_lines = ["- None"]
    if sources:
        source_lines = []
        for source in sources[:20]:
            source_lines.extend(
                [
                    f"- {source['temporal_discovered_source_id']}: {source['source_title']}",
                    f"  - Seed: {source['temporal_seed_id']}",
                    f"  - URL: {source['source_url']}",
                    f"  - Status: {source['http_status']}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Seed: {refusal['temporal_seed_id']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Temporal Web Source Discovery v2",
            "",
            "This lane converts temporal search seeds into public source "
            "candidates or refusals. It does not invent URLs, create quotes, "
            "timestamps, claims, contradictions, production readiness, or "
            "approved evidence.",
            "",
            "## Summary",
            f"- temporal_web_discovery_status: {status}",
            f"- mode: {mode}",
            f"- temporal_seed_count: {seed_count}",
            f"- discovered_source_count: {len(sources)}",
            f"- refusal_count: {len(refusals)}",
            f"- temporal_web_discovery_root: {root}",
            "",
            "## First Discovered Sources",
            *source_lines,
            "",
            "## First Refusals",
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


def build_temporal_web_source_discovery(
    mode: str = "dry-run",
    temporal_seeds_path: Path = DEFAULT_TEMPORAL_SEEDS,
    temporal_summary_path: Path = DEFAULT_TEMPORAL_SUMMARY,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "discover-web"):
        raise ValueError("mode must be dry-run or discover-web")

    temporal_payload = _load_json(temporal_seeds_path)
    temporal_summary = _load_json(temporal_summary_path)
    seeds, seed_lineage = _load_temporal_seeds(temporal_payload)

    schema = _schema()
    validate_schema(schema)
    _validate_upstream_summary(temporal_summary, seeds)
    for seed in seeds:
        validate_temporal_seed(seed)
    _validate_seed_lineage(seeds, seed_lineage)

    sources: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    discovery_lineage: List[Dict[str, Any]] = []
    if mode == "discover-web":
        sources, refusals, discovery_lineage = _discover_sources(seeds)

    source_roots = [source["source_root"] for source in sources]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    lineage_roots = [lineage["lineage_root"] for lineage in discovery_lineage]
    seed_roots_preserved_count = len(discovery_lineage)
    root = _hash_json(
        {
            "source_roots": sorted(source_roots),
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
    status = _status_for(mode, len(sources), len(refusals))
    report = _build_report(status, mode, len(seeds), sources, refusals, root)
    summary = {
        "temporal_web_discovery_status": status,
        "mode": mode,
        "temporal_seed_count": len(seeds),
        "discovered_source_count": len(sources),
        "refusal_count": len(refusals),
        "seed_roots_preserved_count": seed_roots_preserved_count,
        "source_roots": source_roots,
        "refusal_roots": refusal_roots,
        "lineage_roots": lineage_roots,
        "temporal_web_discovery_schema_hash": _hash_json(schema),
        "temporal_web_discovery_report_hash": _sha256_text(report),
        "temporal_web_discovery_root": root,
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
        raise ValueError("temporal web discovery guardrails must remain closed")

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(
        SOURCES_OUTPUT,
        {
            "temporal_discovered_sources": sources,
            "temporal_discovery_lineage": discovery_lineage,
        },
    )
    _write_json(REFUSALS_OUTPUT, {"temporal_web_discovery_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "summary": summary,
        "temporal_discovered_sources": sources,
        "temporal_discovery_lineage": discovery_lineage,
        "temporal_web_discovery_refusals": refusals,
        "schema": schema,
        "report": report,
    }
