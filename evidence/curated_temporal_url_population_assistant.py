#!/usr/bin/env python3
"""
Curated Temporal URL Population Assistant v2.

Searches for candidate URLs for UNSPECIFIED curated temporal source slots. This
lane emits manual-review candidates only and never modifies the curated pack,
invents URLs, creates quotes, timestamps, claims, contradictions, production
readiness, or approved evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse
import hashlib
import html
import http.client
import json
import re
import urllib.error
import urllib.request


DEFAULT_INPUT_PACK = Path("inputs/temporal_sources/duma_boko_temporal_source_pack.json")
DEFAULT_URL_REFUSALS = Path(
    "outputs/curated_temporal_url_resolution/curated_temporal_url_refusals.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/curated_temporal_url_population_assistant")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_url_population_summary.json"
CANDIDATES_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_url_population_candidates.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_url_population_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_url_population_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_url_population_schema.json"

SCHEMA_VERSION = "curated_temporal_url_population_assistant_v2"
UPSTREAM_URL_RESOLUTION_SCHEMA_VERSION = "curated_temporal_url_resolution_v2"

DRY_RUN_STATUS = "TEMPORAL_URL_POPULATION_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "TEMPORAL_URL_POPULATION_CANDIDATE"
PARTIAL_STATUS = "TEMPORAL_URL_POPULATION_PARTIAL"
REFUSED_STATUS = "TEMPORAL_URL_POPULATION_REFUSED"

VERIFICATION_STATUS = "TEMPORAL_URL_CANDIDATE_REQUIRES_MANUAL_REVIEW"
DISCOVERY_METHOD = "duckduckgo_html_public_search_metadata_lookup"
UNSPECIFIED = "UNSPECIFIED"

TIME_DIRECTIONS = ("BEFORE", "AFTER")
SOURCE_TYPES = (
    "MANIFESTO",
    "RALLY_VIDEO",
    "INTERVIEW",
    "OFFICIAL_STATEMENT",
    "GOVERNMENT_UPDATE",
    "MINISTRY_UPDATE",
    "BUDGET_DOCUMENT",
    "PARLIAMENT_RECORD",
    "NEWS_FOLLOWUP",
    "PARTY_WEBSITE",
    "SOCIAL_MEDIA_POST",
)
SOURCE_VERIFICATION_STATUSES = (
    "UNVERIFIED_SOURCE_ENTRY",
    "CURATED_TEMPORAL_SOURCE_REQUIRES_MANUAL_REVIEW",
    "VERIFIED_REACHABLE_TEMPORAL_SOURCE",
)

QUERY_MAP = {
    "MANIFESTO": ("UDC manifesto",),
    "PARTY_WEBSITE": ("UDC campaign statement", "Duma Boko campaign promise"),
    "RALLY_VIDEO": ("Duma Boko rally speech",),
    "INTERVIEW": ("Duma Boko interview",),
    "SOCIAL_MEDIA_POST": ("UDC campaign statement", "Duma Boko campaign promise"),
    "OFFICIAL_STATEMENT": ("Duma Boko government update", "gov.bw Duma Boko"),
    "GOVERNMENT_UPDATE": ("Duma Boko government update", "dailynews.gov.bw Duma Boko"),
    "MINISTRY_UPDATE": ("ministry update Duma Boko",),
    "BUDGET_DOCUMENT": ("budget statement Botswana Duma Boko",),
    "PARLIAMENT_RECORD": ("parliament Botswana Duma Boko",),
    "NEWS_FOLLOWUP": (
        "Mmegi Duma Boko government",
        "Sunday Standard Duma Boko government",
        "Botswana Gazette Duma Boko President",
    ),
}

INPUT_SOURCE_FIELDS = (
    "source_id",
    "time_direction",
    "source_type",
    "url",
    "title",
    "publisher",
    "published_date",
    "topic",
    "linked_claim_id",
    "verification_status",
    "manual_review_required",
    "notes",
)
URL_REFUSAL_FIELDS = (
    "refusal_id",
    "source_id",
    "time_direction",
    "source_type",
    "url",
    "refusal_code",
    "refusal_reason",
    "manual_review_required",
    "refusal_root",
)
CANDIDATE_FIELDS = (
    "candidate_id",
    "source_id",
    "time_direction",
    "source_type",
    "query",
    "candidate_url",
    "title",
    "publisher",
    "http_status",
    "content_type",
    "verification_status",
    "manual_review_required",
    "metadata_hash",
    "candidate_root",
)
REFUSAL_FIELDS = (
    "refusal_id",
    "source_id",
    "time_direction",
    "source_type",
    "query",
    "candidate_url",
    "refusal_code",
    "refusal_reason",
    "http_status",
    "content_type",
    "manual_review_required",
    "refusal_root",
)
REFUSAL_CODES = (
    "REFUSED_INPUT_VALIDATION",
    "REFUSED_NON_UNSPECIFIED_SLOT",
    "REFUSED_MISSING_URL_RESOLUTION_REFUSAL",
    "REFUSED_SEARCH_UNAVAILABLE",
    "REFUSED_NO_PUBLIC_RESULT",
    "REFUSED_SEARCH_RESULT_URL",
    "REFUSED_UNREACHABLE",
    "REFUSED_METADATA_UNVERIFIED",
)


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


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string.")


def _is_public_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _publisher_from_url(value: str) -> str:
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


def _source_stub(source: Optional[Dict[str, Any]]) -> Dict[str, str]:
    if not isinstance(source, dict):
        return {
            "source_id": "UNKNOWN_SOURCE_ID",
            "time_direction": UNSPECIFIED,
            "source_type": UNSPECIFIED,
        }
    return {
        "source_id": str(source.get("source_id") or "UNKNOWN_SOURCE_ID"),
        "time_direction": str(source.get("time_direction") or UNSPECIFIED),
        "source_type": str(source.get("source_type") or UNSPECIFIED),
    }


def _duckduckgo_url(query: str) -> str:
    return f"https://duckduckgo.com/html/?q={quote_plus(query)}"


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


def _fetch_url_text(url: str, timeout: int = 12) -> Tuple[int, str, str, str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; DumaBokoContradictionEngine/2.0; "
                "curated-temporal-url-population-assistant-only)"
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


def _duckduckgo_result_url(raw_href: str, search_url: str) -> str:
    href = html.unescape(raw_href)
    href = urljoin(search_url, href)
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        query = parse_qs(parsed.query)
        uddg = query.get("uddg", [""])[0]
        return unquote(uddg)
    return href


def _search_public_page(query: str, search_cache: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
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
            "content_type": content_type,
            "result_url": "",
            "refusal_code": "REFUSED_SEARCH_UNAVAILABLE",
            "refusal_reason": error or f"Search page returned HTTP status {status}.",
        }
        search_cache[query] = result
        return result
    if not content_type or not page_text:
        result = {
            "search_url": search_url,
            "status": status,
            "content_type": content_type,
            "result_url": "",
            "refusal_code": "REFUSED_SEARCH_UNAVAILABLE",
            "refusal_reason": "Search page did not return usable HTML metadata.",
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
        "search_url": search_url,
        "status": status,
        "content_type": content_type,
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
    if _is_generic_search_url(candidate_url):
        result = (
            None,
            ("REFUSED_SEARCH_RESULT_URL", "Candidate URL is a search-result page.", 0, ""),
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
    if _is_generic_search_url(source_url):
        result = (
            None,
            ("REFUSED_SEARCH_RESULT_URL", "Resolved URL is a search-result page.", status, content_type),
        )
        metadata_cache[candidate_url] = result
        return result
    metadata = {
        "candidate_url": source_url,
        "title": title,
        "publisher": _publisher_from_url(source_url),
        "http_status": status,
        "content_type": content_type,
    }
    result = (metadata, None)
    metadata_cache[candidate_url] = result
    return result


def _validate_source(source: Dict[str, Any]) -> None:
    if not isinstance(source, dict) or set(source.keys()) != set(INPUT_SOURCE_FIELDS):
        raise ValueError("Curated temporal source pack record fields do not match schema.")
    for field_name in INPUT_SOURCE_FIELDS:
        if field_name == "manual_review_required":
            continue
        _require_nonempty_string(source, field_name, "CuratedTemporalSource")
    if source["time_direction"] not in TIME_DIRECTIONS:
        raise ValueError(f"Unsupported time_direction: {source['time_direction']}.")
    if source["source_type"] not in SOURCE_TYPES:
        raise ValueError(f"Unsupported source_type: {source['source_type']}.")
    if source["verification_status"] not in SOURCE_VERIFICATION_STATUSES:
        raise ValueError(f"Unsupported verification_status: {source['verification_status']}.")
    if source["manual_review_required"] is not True:
        raise ValueError("Curated temporal source entries must require manual review.")


def _url_refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _validate_url_refusal(refusal: Dict[str, Any]) -> None:
    if not isinstance(refusal, dict) or set(refusal.keys()) != set(URL_REFUSAL_FIELDS):
        raise ValueError("Curated temporal URL refusal fields do not match upstream schema.")
    for field_name in URL_REFUSAL_FIELDS:
        if field_name == "manual_review_required":
            continue
        _require_nonempty_string(refusal, field_name, "CuratedTemporalUrlRefusal")
    if refusal["manual_review_required"] is not True:
        raise ValueError("CuratedTemporalUrlRefusal.manual_review_required must remain true.")
    if refusal["refusal_root"] != _hash_json(_url_refusal_root_material(refusal)):
        raise ValueError(f"URL refusal_root mismatch for {refusal['source_id']}.")


def _load_and_validate_inputs(
    input_pack_path: Path,
    url_refusals_path: Path,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    pack = _load_json(input_pack_path)
    if not isinstance(pack, dict):
        raise ValueError("Curated temporal source pack must be a JSON object.")
    if pack.get("production_ready") is not False:
        raise ValueError("Curated temporal source pack production_ready must remain false.")
    if pack.get("manual_review_required") is not True:
        raise ValueError("Curated temporal source pack manual_review_required must remain true.")
    sources = pack.get("curated_temporal_sources")
    if not isinstance(sources, list):
        raise ValueError("Curated temporal source pack must contain curated_temporal_sources list.")
    seen_source_ids = set()
    for source in sources:
        _validate_source(source)
        source_id = source["source_id"]
        if source_id in seen_source_ids:
            raise ValueError(f"Duplicate source_id: {source_id}.")
        seen_source_ids.add(source_id)

    refusal_payload = _load_json(url_refusals_path)
    if not isinstance(refusal_payload, dict):
        raise ValueError("Curated temporal URL refusals payload must be a JSON object.")
    if refusal_payload.get("schema_version") != UPSTREAM_URL_RESOLUTION_SCHEMA_VERSION:
        raise ValueError("Curated temporal URL refusals schema_version is unsupported.")
    upstream_refusals = refusal_payload.get("curated_temporal_url_refusals")
    if not isinstance(upstream_refusals, list):
        raise ValueError("Curated temporal URL refusals payload must contain a list.")
    refusal_by_source_id: Dict[str, Dict[str, Any]] = {}
    for refusal in upstream_refusals:
        _validate_url_refusal(refusal)
        source_id = refusal["source_id"]
        if source_id in refusal_by_source_id:
            raise ValueError(f"Duplicate URL-resolution refusal source_id: {source_id}.")
        if source_id not in seen_source_ids:
            raise ValueError(f"URL-resolution refusal references unknown source_id: {source_id}.")
        refusal_by_source_id[source_id] = refusal
    return sources, refusal_by_source_id


def _candidate_metadata_material(candidate: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: candidate[field]
        for field in CANDIDATE_FIELDS
        if field not in ("metadata_hash", "candidate_root")
    }


def _candidate_root_material(candidate: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(candidate)
    material.pop("candidate_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _make_candidate(
    sequence_number: int,
    source: Dict[str, Any],
    query: str,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    candidate = {
        "candidate_id": f"TEMPORAL_URL_POPULATION_CANDIDATE_{sequence_number:06d}",
        "source_id": source["source_id"],
        "time_direction": source["time_direction"],
        "source_type": source["source_type"],
        "query": query,
        "candidate_url": metadata["candidate_url"],
        "title": metadata["title"],
        "publisher": metadata["publisher"],
        "http_status": int(metadata["http_status"]),
        "content_type": metadata["content_type"],
        "verification_status": VERIFICATION_STATUS,
        "manual_review_required": True,
        "metadata_hash": "",
        "candidate_root": "",
    }
    candidate["metadata_hash"] = _hash_json(_candidate_metadata_material(candidate))
    candidate["candidate_root"] = _hash_json(_candidate_root_material(candidate))
    return candidate


def _make_refusal(
    sequence_number: int,
    source: Optional[Dict[str, Any]],
    query: str,
    candidate_url: str,
    code: str,
    reason: str,
    http_status: int = 0,
    content_type: str = "",
) -> Dict[str, Any]:
    stub = _source_stub(source)
    refusal = {
        "refusal_id": f"TEMPORAL_URL_POPULATION_REFUSAL_{sequence_number:06d}",
        "source_id": stub["source_id"],
        "time_direction": stub["time_direction"],
        "source_type": stub["source_type"],
        "query": query or UNSPECIFIED,
        "candidate_url": candidate_url or UNSPECIFIED,
        "refusal_code": code,
        "refusal_reason": reason,
        "http_status": int(http_status),
        "content_type": content_type or UNSPECIFIED,
        "manual_review_required": True,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_candidate(candidate: Dict[str, Any]) -> None:
    if set(candidate.keys()) != set(CANDIDATE_FIELDS):
        raise ValueError("Temporal URL population candidate fields changed unexpectedly.")
    for field_name in CANDIDATE_FIELDS:
        if field_name in ("http_status", "manual_review_required"):
            continue
        _require_nonempty_string(candidate, field_name, "TemporalUrlPopulationCandidate")
    if candidate["time_direction"] not in TIME_DIRECTIONS:
        raise ValueError("TemporalUrlPopulationCandidate.time_direction unsupported.")
    if candidate["source_type"] not in SOURCE_TYPES:
        raise ValueError("TemporalUrlPopulationCandidate.source_type unsupported.")
    if not _is_public_url(candidate["candidate_url"]):
        raise ValueError("TemporalUrlPopulationCandidate.candidate_url must be public HTTP(S).")
    if _is_generic_search_url(candidate["candidate_url"]):
        raise ValueError("TemporalUrlPopulationCandidate.candidate_url cannot be a search page.")
    if not isinstance(candidate["http_status"], int) or not (200 <= candidate["http_status"] < 400):
        raise ValueError("TemporalUrlPopulationCandidate.http_status must be 200-399.")
    if candidate["verification_status"] != VERIFICATION_STATUS:
        raise ValueError("TemporalUrlPopulationCandidate.verification_status unsupported.")
    if candidate["manual_review_required"] is not True:
        raise ValueError("TemporalUrlPopulationCandidate.manual_review_required must remain true.")
    if candidate["metadata_hash"] != _hash_json(_candidate_metadata_material(candidate)):
        raise ValueError(f"metadata_hash mismatch for {candidate['candidate_id']}.")
    if candidate["candidate_root"] != _hash_json(_candidate_root_material(candidate)):
        raise ValueError(f"candidate_root mismatch for {candidate['candidate_id']}.")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Temporal URL population refusal fields changed unexpectedly.")
    for field_name in REFUSAL_FIELDS:
        if field_name in ("http_status", "manual_review_required"):
            continue
        _require_nonempty_string(refusal, field_name, "TemporalUrlPopulationRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError("TemporalUrlPopulationRefusal.refusal_code unsupported.")
    if not isinstance(refusal["http_status"], int):
        raise ValueError("TemporalUrlPopulationRefusal.http_status must be an integer.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("TemporalUrlPopulationRefusal.manual_review_required must remain true.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}.")


def _queries_for_source(source: Dict[str, Any]) -> Tuple[str, ...]:
    return QUERY_MAP.get(source["source_type"], ())


def _eligible_sources(
    sources: List[Dict[str, Any]],
    refusal_by_source_id: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    eligible: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    for source in sources:
        source_id = source["source_id"]
        if source["url"] != UNSPECIFIED:
            refusals.append(
                _make_refusal(
                    len(refusals) + 1,
                    source,
                    UNSPECIFIED,
                    source["url"],
                    "REFUSED_NON_UNSPECIFIED_SLOT",
                    "Source slot already has a URL and is outside this assistant lane.",
                )
            )
            continue
        upstream_refusal = refusal_by_source_id.get(source_id)
        if not upstream_refusal:
            refusals.append(
                _make_refusal(
                    len(refusals) + 1,
                    source,
                    UNSPECIFIED,
                    UNSPECIFIED,
                    "REFUSED_MISSING_URL_RESOLUTION_REFUSAL",
                    "No URL-resolution refusal was found for this UNSPECIFIED source slot.",
                )
            )
            continue
        if upstream_refusal["refusal_code"] != "REFUSED_UNSPECIFIED_URL":
            refusals.append(
                _make_refusal(
                    len(refusals) + 1,
                    source,
                    UNSPECIFIED,
                    source["url"],
                    "REFUSED_INPUT_VALIDATION",
                    "URL-resolution refusal was not REFUSED_UNSPECIFIED_URL.",
                )
            )
            continue
        eligible.append(source)
    return eligible, refusals


def _build_candidates_and_refusals(
    sources: List[Dict[str, Any]],
    refusal_by_source_id: Dict[str, Dict[str, Any]],
    mode: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    preflight_eligible, preflight_refusals = _eligible_sources(sources, refusal_by_source_id)
    if mode == "dry-run":
        return [], [], len(preflight_eligible)

    candidates: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = list(preflight_refusals)
    search_cache: Dict[str, Dict[str, Any]] = {}
    metadata_cache: Dict[str, Tuple[Optional[Dict[str, Any]], Optional[Tuple[str, str, int, str]]]] = {}

    for source in preflight_eligible:
        queries = _queries_for_source(source)
        if not queries:
            refusals.append(
                _make_refusal(
                    len(refusals) + 1,
                    source,
                    UNSPECIFIED,
                    UNSPECIFIED,
                    "REFUSED_INPUT_VALIDATION",
                    "No source-specific query mapping exists for this source_type.",
                )
            )
            continue
        for query in queries:
            search_result = _search_public_page(query, search_cache)
            search_refusal_code = search_result.get("refusal_code")
            if search_refusal_code == "REFUSED_SEARCH_UNAVAILABLE":
                refusals.append(
                    _make_refusal(
                        len(refusals) + 1,
                        source,
                        query,
                        str(search_result.get("search_url") or _duckduckgo_url(query)),
                        "REFUSED_SEARCH_UNAVAILABLE",
                        str(search_result.get("refusal_reason") or "Search page was unavailable."),
                        http_status=int(search_result.get("status") or 0),
                        content_type=str(search_result.get("content_type") or ""),
                    )
                )
                continue
            result_url = str(search_result.get("result_url") or "")
            if not result_url:
                refusals.append(
                    _make_refusal(
                        len(refusals) + 1,
                        source,
                        query,
                        str(search_result.get("search_url") or _duckduckgo_url(query)),
                        "REFUSED_NO_PUBLIC_RESULT",
                        str(search_result.get("refusal_reason") or "No public result URL was returned."),
                        http_status=int(search_result.get("status") or 0),
                        content_type=str(search_result.get("content_type") or ""),
                    )
                )
                continue
            metadata, metadata_refusal = _verify_candidate_url(result_url, metadata_cache)
            if metadata_refusal is not None:
                code, reason, http_status, content_type = metadata_refusal
                refusals.append(
                    _make_refusal(
                        len(refusals) + 1,
                        source,
                        query,
                        result_url,
                        code,
                        reason,
                        http_status=http_status,
                        content_type=content_type,
                    )
                )
                continue
            if metadata is None:
                refusals.append(
                    _make_refusal(
                        len(refusals) + 1,
                        source,
                        query,
                        result_url,
                        "REFUSED_METADATA_UNVERIFIED",
                        "Candidate URL metadata could not be verified.",
                    )
                )
                continue
            candidates.append(_make_candidate(len(candidates) + 1, source, query, metadata))

    for candidate in candidates:
        validate_candidate(candidate)
    for refusal in refusals:
        validate_refusal(refusal)
    return candidates, refusals, len(preflight_eligible)


def _status_for(mode: str, candidate_count: int, refusal_count: int) -> str:
    if mode == "dry-run" and refusal_count == 0:
        return DRY_RUN_STATUS
    if candidate_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if candidate_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _schema_payload() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_fields": list(CANDIDATE_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "allowed_time_direction": list(TIME_DIRECTIONS),
        "allowed_source_type": list(SOURCE_TYPES),
        "query_map": {key: list(value) for key, value in QUERY_MAP.items()},
        "verification_status": VERIFICATION_STATUS,
        "discovery_method": DISCOVERY_METHOD,
        "refusal_codes": list(REFUSAL_CODES),
        "guardrails": {
            "approved_evidence": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "production_ready": False,
            "quotes_created": 0,
            "timestamps_created": 0,
            "urls_invented": 0,
        },
    }


def _summary_root_material(summary: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {
        "temporal_url_population_root",
        "temporal_url_population_schema_hash",
        "temporal_url_population_report_hash",
    }
    return {key: value for key, value in summary.items() if key not in excluded}


def _build_report(
    status: str,
    mode: str,
    input_source_count: int,
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
                    f"- {candidate['candidate_id']}",
                    f"  - Source: {candidate['source_id']}",
                    f"  - Query: {candidate['query']}",
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
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Source: {refusal['source_id']}",
                    f"  - Query: {refusal['query']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Curated Temporal URL Population Assistant v2",
            "",
            "This lane searches for candidate URLs for UNSPECIFIED curated temporal "
            "source slots. It emits manual-review candidates only and does not "
            "modify the curated source pack.",
            "",
            "## Summary",
            f"- temporal_url_population_status: {status}",
            f"- mode: {mode}",
            f"- input_source_count: {input_source_count}",
            f"- candidate_url_count: {len(candidates)}",
            f"- refusal_count: {len(refusals)}",
            f"- temporal_url_population_root: {root}",
            "",
            "## First Candidate URLs",
            *candidate_lines,
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


def build_curated_temporal_url_population_assistant(
    mode: str = "dry-run",
    input_pack_path: Path = DEFAULT_INPUT_PACK,
    url_refusals_path: Path = DEFAULT_URL_REFUSALS,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "search-candidates"):
        raise ValueError("mode must be 'dry-run' or 'search-candidates'.")

    sources, refusal_by_source_id = _load_and_validate_inputs(input_pack_path, url_refusals_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates, refusals, eligible_source_count = _build_candidates_and_refusals(
        sources, refusal_by_source_id, mode
    )
    status = _status_for(mode, len(candidates), len(refusals))
    schema = _schema_payload()
    schema_hash = _hash_json(schema)

    summary = {
        "temporal_url_population_status": status,
        "mode": mode,
        "input_source_count": len(sources),
        "eligible_unspecified_source_count": eligible_source_count,
        "candidate_url_count": len(candidates),
        "refusal_count": len(refusals),
        "unique_query_count": len({query for source in sources for query in _queries_for_source(source)}),
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "candidate_roots": [candidate["candidate_root"] for candidate in candidates],
        "refusal_roots": [refusal["refusal_root"] for refusal in refusals],
        "temporal_url_population_schema_hash": schema_hash,
        "temporal_url_population_report_hash": "",
        "temporal_url_population_root": "",
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
        "curated_pack_modified": False,
        "no_generated_outputs_committed": True,
    }
    summary["temporal_url_population_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(sources),
        candidates,
        refusals,
        summary["temporal_url_population_root"],
    )
    summary["temporal_url_population_report_hash"] = _sha256_text(report)
    summary["temporal_url_population_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(sources),
        candidates,
        refusals,
        summary["temporal_url_population_root"],
    )

    candidates_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "temporal_url_population_candidates": candidates,
    }
    refusals_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "temporal_url_population_refusals": refusals,
    }

    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(output_dir / CANDIDATES_OUTPUT.name, candidates_payload)
    _write_json(output_dir / REFUSALS_OUTPUT.name, refusals_payload)
    _write_json(output_dir / SCHEMA_OUTPUT.name, schema)
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    return {
        "summary": summary,
        "temporal_url_population_candidates": candidates,
        "temporal_url_population_refusals": refusals,
        "schema": schema,
        "report": report,
    }


__all__ = ["build_curated_temporal_url_population_assistant"]
