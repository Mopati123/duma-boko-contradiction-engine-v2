#!/usr/bin/env python3
"""
Registry Source Discovery Engine v2.

Discovers registry-level public endpoints only. This lane does not create
evidence packets, quotes, timestamps, transcript lines, claims, contradictions,
or downstream reports.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
import hashlib
import html
import json
import re
import urllib.error
import urllib.request


DEFAULT_REGISTRY_INPUT = Path("inputs/source_registry/duma_boko_source_registry.json")
DEFAULT_VALIDATED_REGISTRY = Path(
    "outputs/canonical_source_registry_engine/validated_source_registry.json"
)
DEFAULT_RESEARCH_SUMMARY = Path("docs/research/Duma_Boko_Investigation_Cases_Summary.md")
DEFAULT_DISCOVERY_SEEDS = Path("inputs/evidence_discovery/duma_boko_discovery_seeds.json")

DEFAULT_OUTPUT_DIR = Path("outputs/registry_source_discovery_engine")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "registry_source_discovery_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "registry_source_discovery_summary.json"
DISCOVERED_OUTPUT = DEFAULT_OUTPUT_DIR / "discovered_registry_sources.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "registry_source_discovery_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "registry_source_discovery_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "registry_source_discovery_schema.json"

SCHEMA_VERSION = "registry_source_discovery_engine_v2"
UPSTREAM_SCHEMA_VERSION = "canonical_source_registry_engine_v2"
UPSTREAM_STATUS = "CANONICAL_SOURCE_REGISTRY_CANDIDATE"

DEMO_STATUS = "REGISTRY_SOURCE_DISCOVERY_DEMO_CANDIDATE"
CANDIDATE_STATUS = "REGISTRY_SOURCE_DISCOVERY_CANDIDATE"
PARTIAL_STATUS = "REGISTRY_SOURCE_DISCOVERY_PARTIAL"
REFUSED_STATUS = "REGISTRY_SOURCE_DISCOVERY_REFUSED"

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

VERIFICATION_STATUSES = (
    "DEMO_UNVERIFIED",
    "DISCOVERED_REQUIRES_MANUAL_REVIEW",
    "VERIFIED_REACHABLE_PUBLIC_ENDPOINT",
    "REFUSED_NOT_FOUND",
    "REFUSED_UNREACHABLE",
    "REFUSED_LOGIN_REQUIRED",
    "REFUSED_METADATA_UNVERIFIED",
    "REFUSED_UNSUPPORTED_PLATFORM",
)

DISCOVERED_FIELDS = (
    "discovered_registry_source_id",
    "source_name",
    "source_category",
    "platform",
    "base_url",
    "resolved_url",
    "search_query",
    "discovery_method",
    "http_status",
    "content_type",
    "source_owner",
    "trust_tier",
    "verification_status",
    "manual_review_required",
    "reasoning_summary",
    "metadata_hash",
    "discovered_registry_source_root",
)

REFUSAL_FIELDS = (
    "refusal_id",
    "discovery_target_id",
    "source_name",
    "source_category",
    "platform",
    "search_query",
    "refusal_code",
    "refusal_reason",
    "manual_review_required",
    "refusal_root",
)

SEARCH_TARGET_FIELDS = (
    "discovery_target_id",
    "source_name",
    "source_category",
    "platform",
    "search_query",
    "trust_tier",
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

VALIDATED_SOURCE_FIELDS = REGISTRY_SOURCE_FIELDS + ("registry_source_root",)


def _search_targets() -> List[Dict[str, Any]]:
    return [
        {
            "discovery_target_id": "REGISTRY_DISCOVERY_TARGET_001",
            "source_name": "Duma Boko official website",
            "source_category": "manual_review_source",
            "platform": "public_web_search",
            "search_query": '"Duma Boko" official website',
            "trust_tier": 2,
        },
        {
            "discovery_target_id": "REGISTRY_DISCOVERY_TARGET_002",
            "source_name": "Duma Boko official Facebook",
            "source_category": "facebook_page",
            "platform": "facebook",
            "search_query": '"Duma Boko" official Facebook',
            "trust_tier": 2,
        },
        {
            "discovery_target_id": "REGISTRY_DISCOVERY_TARGET_003",
            "source_name": "Duma Boko YouTube",
            "source_category": "youtube_channel",
            "platform": "youtube",
            "search_query": '"Duma Boko" YouTube',
            "trust_tier": 2,
        },
        {
            "discovery_target_id": "REGISTRY_DISCOVERY_TARGET_004",
            "source_name": "Umbrella for Democratic Change official website",
            "source_category": "official_party",
            "platform": "public_web_search",
            "search_query": '"Umbrella for Democratic Change" official website',
            "trust_tier": 1,
        },
        {
            "discovery_target_id": "REGISTRY_DISCOVERY_TARGET_005",
            "source_name": "Umbrella for Democratic Change Facebook",
            "source_category": "facebook_page",
            "platform": "facebook",
            "search_query": '"Umbrella for Democratic Change" Facebook',
            "trust_tier": 2,
        },
        {
            "discovery_target_id": "REGISTRY_DISCOVERY_TARGET_006",
            "source_name": "Umbrella for Democratic Change YouTube",
            "source_category": "youtube_channel",
            "platform": "youtube",
            "search_query": '"Umbrella for Democratic Change" YouTube',
            "trust_tier": 2,
        },
        {
            "discovery_target_id": "REGISTRY_DISCOVERY_TARGET_007",
            "source_name": "Botswana Parliament Hansard Duma Boko",
            "source_category": "parliament_record",
            "platform": "parliament_record_search",
            "search_query": '"Botswana Parliament" Hansard Duma Boko',
            "trust_tier": 1,
        },
        {
            "discovery_target_id": "REGISTRY_DISCOVERY_TARGET_008",
            "source_name": "Botswana Parliament Duma Boko",
            "source_category": "parliament_record",
            "platform": "parliament_record_search",
            "search_query": '"Botswana Parliament" Duma Boko',
            "trust_tier": 1,
        },
        {
            "discovery_target_id": "REGISTRY_DISCOVERY_TARGET_009",
            "source_name": "Mmegi Duma Boko archive",
            "source_category": "news_publisher",
            "platform": "news_archive_search",
            "search_query": '"Duma Boko" Mmegi',
            "trust_tier": 3,
        },
        {
            "discovery_target_id": "REGISTRY_DISCOVERY_TARGET_010",
            "source_name": "Sunday Standard Duma Boko archive",
            "source_category": "news_publisher",
            "platform": "news_archive_search",
            "search_query": '"Duma Boko" Sunday Standard',
            "trust_tier": 3,
        },
        {
            "discovery_target_id": "REGISTRY_DISCOVERY_TARGET_011",
            "source_name": "Botswana Gazette Duma Boko archive",
            "source_category": "news_publisher",
            "platform": "news_archive_search",
            "search_query": '"Duma Boko" Botswana Gazette',
            "trust_tier": 3,
        },
        {
            "discovery_target_id": "REGISTRY_DISCOVERY_TARGET_012",
            "source_name": "BTV Duma Boko archive",
            "source_category": "radio_tv_broadcaster",
            "platform": "broadcast_archive_search",
            "search_query": '"Duma Boko" BTV',
            "trust_tier": 2,
        },
        {
            "discovery_target_id": "REGISTRY_DISCOVERY_TARGET_013",
            "source_name": "Radio Botswana Duma Boko archive",
            "source_category": "radio_tv_broadcaster",
            "platform": "broadcast_archive_search",
            "search_query": '"Duma Boko" Radio Botswana',
            "trust_tier": 2,
        },
        {
            "discovery_target_id": "REGISTRY_DISCOVERY_TARGET_014",
            "source_name": "Yarona FM Duma Boko archive",
            "source_category": "radio_tv_broadcaster",
            "platform": "broadcast_archive_search",
            "search_query": '"Duma Boko" Yarona FM',
            "trust_tier": 3,
        },
        {
            "discovery_target_id": "REGISTRY_DISCOVERY_TARGET_015",
            "source_name": "Gabz FM Duma Boko archive",
            "source_category": "radio_tv_broadcaster",
            "platform": "broadcast_archive_search",
            "search_query": '"Duma Boko" Gabz FM',
            "trust_tier": 3,
        },
    ]


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


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "registry_source_discovery_only": True,
        "discovered_registry_source_fields": list(DISCOVERED_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "search_target_fields": list(SEARCH_TARGET_FIELDS),
        "source_categories": list(SOURCE_CATEGORIES),
        "verification_statuses": list(VERIFICATION_STATUSES),
        "dry_run_behavior": "Dry-run emits 15 deterministic demo candidates without network access.",
        "discover_web_behavior": (
            "Discover-web uses accessible public search pages and direct HTTP checks only. "
            "It does not infer URLs or process evidence."
        ),
        "prohibited_outputs": {
            "quotes_created": 0,
            "timestamps_created": 0,
            "transcripts_created": 0,
            "claims_created": 0,
            "contradictions_created": 0,
        },
        "root_rules": {
            "metadata_hash": "sha256 over deterministic discovered source metadata excluding roots",
            "discovered_registry_source_root": (
                "sha256 over discovered source excluding discovered_registry_source_root"
            ),
            "refusal_root": "sha256 over refusal excluding refusal_root",
            "registry_source_discovery_root": (
                "sha256 over sorted discovered source roots, sorted refusal roots, and closed flags"
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
        raise ValueError("registry_source_discovery_schema schema_version changed")
    if schema.get("discovered_registry_source_fields") != list(DISCOVERED_FIELDS):
        raise ValueError("discovered_registry_source_fields changed")
    if schema.get("refusal_fields") != list(REFUSAL_FIELDS):
        raise ValueError("refusal_fields changed")


def _metadata_material(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: record[field]
        for field in DISCOVERED_FIELDS
        if field not in ("metadata_hash", "discovered_registry_source_root")
    }


def _root_material(record: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(record)
    material.pop("discovered_registry_source_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _make_discovered_source(
    target: Dict[str, Any],
    base_url: str,
    resolved_url: str,
    discovery_method: str,
    http_status: int,
    content_type: str,
    source_owner: str,
    verification_status: str,
    reasoning_summary: str,
) -> Dict[str, Any]:
    record = {
        "discovered_registry_source_id": f"DISCOVERED_{target['discovery_target_id']}",
        "source_name": target["source_name"],
        "source_category": target["source_category"],
        "platform": target["platform"],
        "base_url": base_url,
        "resolved_url": resolved_url,
        "search_query": target["search_query"],
        "discovery_method": discovery_method,
        "http_status": int(http_status),
        "content_type": content_type,
        "source_owner": source_owner,
        "trust_tier": int(target["trust_tier"]),
        "verification_status": verification_status,
        "manual_review_required": True,
        "reasoning_summary": reasoning_summary,
        "metadata_hash": "",
        "discovered_registry_source_root": "",
    }
    record["metadata_hash"] = _hash_json(_metadata_material(record))
    record["discovered_registry_source_root"] = _hash_json(_root_material(record))
    return record


def _make_refusal(target: Dict[str, Any], code: str, reason: str) -> Dict[str, Any]:
    refusal = {
        "refusal_id": f"REGISTRY_SOURCE_DISCOVERY_REFUSAL_{target['discovery_target_id']}",
        "discovery_target_id": target["discovery_target_id"],
        "source_name": target["source_name"],
        "source_category": target["source_category"],
        "platform": target["platform"],
        "search_query": target["search_query"],
        "refusal_code": code,
        "refusal_reason": reason,
        "manual_review_required": True,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_search_target(target: Dict[str, Any]) -> None:
    if set(target.keys()) != set(SEARCH_TARGET_FIELDS):
        raise ValueError("Search target fields changed unexpectedly")
    for field_name in (
        "discovery_target_id",
        "source_name",
        "source_category",
        "platform",
        "search_query",
    ):
        _require_nonempty_string(target, field_name, "RegistrySourceDiscoveryTarget")
    if target["source_category"] not in SOURCE_CATEGORIES:
        raise ValueError(f"Unsupported source_category: {target['source_category']}")
    if not isinstance(target.get("trust_tier"), int) or target["trust_tier"] not in (1, 2, 3, 4):
        raise ValueError("Search target trust_tier must be 1-4")


def validate_discovered_source(record: Dict[str, Any]) -> None:
    if set(record.keys()) != set(DISCOVERED_FIELDS):
        raise ValueError("Discovered registry source fields changed unexpectedly")
    for field_name in (
        "discovered_registry_source_id",
        "source_name",
        "source_category",
        "platform",
        "base_url",
        "resolved_url",
        "search_query",
        "discovery_method",
        "content_type",
        "source_owner",
        "verification_status",
        "reasoning_summary",
        "metadata_hash",
        "discovered_registry_source_root",
    ):
        _require_nonempty_string(record, field_name, "DiscoveredRegistrySource")
    if record["source_category"] not in SOURCE_CATEGORIES:
        raise ValueError(f"Unsupported source_category: {record['source_category']}")
    if record["verification_status"] not in VERIFICATION_STATUSES:
        raise ValueError(f"Unsupported verification_status: {record['verification_status']}")
    if record["manual_review_required"] is not True:
        raise ValueError("DiscoveredRegistrySource.manual_review_required must remain true")
    if not isinstance(record["trust_tier"], int):
        raise ValueError("DiscoveredRegistrySource.trust_tier must be an integer")
    if not isinstance(record["http_status"], int):
        raise ValueError("DiscoveredRegistrySource.http_status must be an integer")
    if record["verification_status"] == "VERIFIED_REACHABLE_PUBLIC_ENDPOINT":
        if not _is_public_url(record["resolved_url"]):
            raise ValueError("Verified discovered source resolved_url must be public")
        if record["http_status"] < 200 or record["http_status"] >= 400:
            raise ValueError("Verified discovered source http_status must be 200-399")
    if record["metadata_hash"] != _hash_json(_metadata_material(record)):
        raise ValueError(f"metadata_hash mismatch for {record['discovered_registry_source_id']}")
    if record["discovered_registry_source_root"] != _hash_json(_root_material(record)):
        raise ValueError(f"root mismatch for {record['discovered_registry_source_id']}")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Registry source discovery refusal fields changed unexpectedly")
    for field_name in (
        "refusal_id",
        "discovery_target_id",
        "source_name",
        "source_category",
        "platform",
        "search_query",
        "refusal_code",
        "refusal_reason",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "RegistrySourceDiscoveryRefusal")
    if refusal["refusal_code"] not in VERIFICATION_STATUSES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}")
    if not refusal["refusal_code"].startswith("REFUSED_"):
        raise ValueError("Refusal code must be a REFUSED_* status")
    if refusal["manual_review_required"] is not True:
        raise ValueError("RegistrySourceDiscoveryRefusal.manual_review_required must be true")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}")


def _validate_upstream(
    registry_input: Dict[str, Any],
    validated_registry: Dict[str, Any],
    research_summary_path: Path,
    discovery_seeds: Dict[str, Any],
) -> None:
    if not registry_input:
        raise ValueError("source registry input is missing")
    if not validated_registry:
        raise ValueError("validated source registry output is missing")
    if not research_summary_path.exists() or not research_summary_path.read_text(encoding="utf-8").strip():
        raise ValueError("research summary Markdown is missing or empty")
    if not discovery_seeds:
        raise ValueError("discovery seed input is missing")
    if registry_input.get("registry_version") != "canonical_source_registry_engine_v2":
        raise ValueError("source registry input version is invalid")
    if validated_registry.get("schema_version") != "canonical_source_registry_engine_v2":
        raise ValueError("validated source registry schema is invalid")
    if validated_registry.get("source_registry_status") != "CANONICAL_SOURCE_REGISTRY_CANDIDATE":
        raise ValueError("validated source registry status is invalid")
    registry_sources = registry_input.get("registry_sources")
    validated_sources = validated_registry.get("validated_source_registry")
    if not isinstance(registry_sources, list) or len(registry_sources) != 20:
        raise ValueError("source registry input must contain 20 sources")
    if not isinstance(validated_sources, list) or len(validated_sources) != 20:
        raise ValueError("validated source registry must contain 20 sources")
    seed_records = discovery_seeds.get("discovery_seeds")
    if not isinstance(seed_records, list) or len(seed_records) != 60:
        raise ValueError("discovery seed input must contain 60 seeds")


def _fetch_url_text(url: str) -> Tuple[str, str, int, str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; RegistrySourceDiscovery/2.0; "
                "source-endpoint-discovery-only)"
            )
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            content_type = response.headers.get("content-type", "")
            raw = response.read(800000)
            text = raw.decode("utf-8", errors="replace")
            return text, response.geturl(), response.status, content_type, ""
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return "", "", 0, "", str(exc)


def _duckduckgo_result_url(raw_href: str) -> str:
    href = html.unescape(raw_href)
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        query = parse_qs(parsed.query)
        return unquote(query.get("uddg", [""])[0])
    return href


def _search_public_page(query: str) -> Tuple[str, str]:
    search_url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    text, _final_url, status, _content_type, error = _fetch_url_text(search_url)
    if error:
        return "", error
    if status < 200 or status >= 400:
        return "", f"Search page returned HTTP status {status}"
    links = re.findall(
        r'<a[^>]+class=["\'][^"\']*result__a[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
        text,
        flags=re.IGNORECASE,
    )
    for raw_href in links:
        result_url = _duckduckgo_result_url(raw_href)
        if _is_public_url(result_url):
            return result_url, ""
    return "", "No public endpoint result was returned by the accessible search page."


def _is_login_required(url: str, page_text: str) -> bool:
    lowered_url = url.lower()
    lowered_text = page_text.lower()
    login_markers = (
        "/login",
        "login?",
        "sign in",
        "log in",
        "create an account",
        "login required",
    )
    if any(marker in lowered_url for marker in ("/login", "login?", "/i/flow/login")):
        return True
    return any(marker in lowered_text for marker in login_markers)


def _verify_candidate_url(target: Dict[str, Any], url: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if not _is_public_url(url):
        return None, _make_refusal(target, "REFUSED_METADATA_UNVERIFIED", "Search result URL is not public HTTP(S).")
    text, final_url, status, content_type, error = _fetch_url_text(url)
    if error:
        return None, _make_refusal(target, "REFUSED_UNREACHABLE", error)
    if status < 200 or status >= 400:
        return None, _make_refusal(target, "REFUSED_UNREACHABLE", f"Endpoint returned HTTP status {status}.")
    if _is_login_required(final_url, text):
        return None, _make_refusal(target, "REFUSED_LOGIN_REQUIRED", "Endpoint appears to require login.")
    parsed = urlparse(final_url)
    record = _make_discovered_source(
        target,
        url,
        final_url,
        "public_search_page_result_http_get",
        status,
        content_type or "UNVERIFIED_PENDING_MANUAL_REVIEW",
        parsed.netloc.lower(),
        "DISCOVERED_REQUIRES_MANUAL_REVIEW",
        "Public search returned a reachable endpoint. It remains candidate-only pending manual review.",
    )
    return record, None


def _discover_target(target: Dict[str, Any], mode: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    validate_search_target(target)
    if mode == "dry-run":
        return (
            _make_discovered_source(
                target,
                UNSPECIFIED,
                UNSPECIFIED,
                "deterministic_demo_candidate",
                0,
                UNSPECIFIED,
                UNSPECIFIED,
                "DEMO_UNVERIFIED",
                "Dry-run demonstration candidate only; no live URL verification was attempted.",
            ),
            None,
        )
    result_url, error = _search_public_page(target["search_query"])
    if not result_url:
        return None, _make_refusal(target, "REFUSED_NOT_FOUND", error or "No public endpoint found.")
    return _verify_candidate_url(target, result_url)


def _status_for(mode: str, discovered_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DEMO_STATUS
    if discovered_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if discovered_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _build_report(
    status: str,
    mode: str,
    discovered_sources: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    discovered_lines = ["- None"]
    if discovered_sources:
        discovered_lines = []
        for source in discovered_sources:
            discovered_lines.extend(
                [
                    f"- {source['discovered_registry_source_id']}",
                    f"  - Source: {source['source_name']}",
                    f"  - Resolved URL: {source['resolved_url']}",
                    f"  - Verification Status: {source['verification_status']}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Source: {refusal['source_name']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    lines = [
        "# Registry Source Discovery Engine v2",
        "",
        "This lane discovers source endpoints only. It does not extract quotes, "
        "timestamps, transcript lines, evidence packets, claims, contradictions, "
        "or final case reports.",
        "",
        "## Summary",
        f"- registry_source_discovery_status: {status}",
        f"- mode: {mode}",
        f"- candidate_registry_source_count: {len(discovered_sources)}",
        f"- refusal_count: {len(refusals)}",
        f"- registry_source_discovery_root: {root}",
        "",
        "## Discovered Registry Sources",
        *discovered_lines,
        "",
        "## Refusals",
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
        "",
    ]
    return "\n".join(lines)


def build_registry_source_discovery_engine(
    mode: str = "dry-run",
    registry_input_path: Path = DEFAULT_REGISTRY_INPUT,
    validated_registry_path: Path = DEFAULT_VALIDATED_REGISTRY,
    research_summary_path: Path = DEFAULT_RESEARCH_SUMMARY,
    discovery_seeds_path: Path = DEFAULT_DISCOVERY_SEEDS,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "discover-web"):
        raise ValueError("mode must be dry-run or discover-web")
    registry_input = _load_json(registry_input_path)
    validated_registry = _load_json(validated_registry_path)
    discovery_seeds = _load_json(discovery_seeds_path)
    _validate_upstream(registry_input, validated_registry, research_summary_path, discovery_seeds)
    schema = _schema()
    validate_schema(schema)

    discovered_sources: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    for target in _search_targets():
        discovered, refusal = _discover_target(target, mode)
        if discovered is not None:
            validate_discovered_source(discovered)
            discovered_sources.append(discovered)
        if refusal is not None:
            validate_refusal(refusal)
            refusals.append(refusal)

    discovered_roots = [source["discovered_registry_source_root"] for source in discovered_sources]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    root = _hash_json(
        {
            "discovered_registry_source_roots": sorted(discovered_roots),
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
    status = _status_for(mode, len(discovered_sources), len(refusals))
    verified_public_endpoint_count = sum(
        1
        for source in discovered_sources
        if source["verification_status"] == "VERIFIED_REACHABLE_PUBLIC_ENDPOINT"
    )
    manual_review_required_count = sum(
        1 for source in discovered_sources if source["manual_review_required"] is True
    )
    report = _build_report(status, mode, discovered_sources, refusals, root)
    summary = {
        "registry_source_discovery_status": status,
        "mode": mode,
        "candidate_registry_source_count": len(discovered_sources),
        "verified_public_endpoint_count": verified_public_endpoint_count,
        "manual_review_required_count": manual_review_required_count,
        "refusal_count": len(refusals),
        "quotes_created": 0,
        "timestamps_created": 0,
        "transcripts_created": 0,
        "claims_created": 0,
        "contradictions_created": 0,
        "evidence_approved_count": 0,
        "discovered_registry_source_roots": discovered_roots,
        "refusal_roots": refusal_roots,
        "registry_source_discovery_schema_hash": _hash_json(schema),
        "registry_source_discovery_report_hash": _sha256_text(report),
        "registry_source_discovery_root": root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    if mode == "dry-run":
        if summary["candidate_registry_source_count"] != 15:
            raise ValueError("Dry-run must emit exactly 15 demo candidates")
        if summary["verified_public_endpoint_count"] != 0:
            raise ValueError("Dry-run must not verify public endpoints")
        if summary["refusal_count"] != 0:
            raise ValueError("Dry-run must not emit refusals")
    if not _closed_flags(summary):
        raise ValueError("Registry source discovery guardrails must remain closed")

    status_payload = {
        "records": [
            {
                "registry_source_discovery_status": status,
                "candidate_registry_source_count": len(discovered_sources),
                "verified_public_endpoint_count": verified_public_endpoint_count,
                "manual_review_required_count": manual_review_required_count,
                "refusal_count": len(refusals),
                "registry_source_discovery_root": root,
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
    _write_json(DISCOVERED_OUTPUT, {"discovered_registry_sources": discovered_sources})
    _write_json(REFUSALS_OUTPUT, {"registry_source_discovery_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "payload": status_payload,
        "summary": summary,
        "discovered_registry_sources": discovered_sources,
        "registry_source_discovery_refusals": refusals,
        "schema": schema,
        "report": report,
    }
