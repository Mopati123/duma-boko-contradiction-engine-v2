#!/usr/bin/env python3
"""
Web Source Discovery Engine v2.

Transforms discovery seeds into resolved candidate web source records or
deterministic refusal records. This lane is source-discovery only: it does not
extract quotes, timestamps, transcript lines, evidence approvals, or
contradiction findings.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request


DEFAULT_DISCOVERY_INPUT = Path("inputs/evidence_discovery/duma_boko_discovery_seeds.json")
DEFAULT_VALIDATED_DISCOVERY_SEEDS = Path(
    "outputs/discovery_seed_pack_loader/validated_discovery_seeds.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/web_source_discovery_engine")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "web_source_discovery_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "web_source_discovery_summary.json"
RESOLVED_OUTPUT = DEFAULT_OUTPUT_DIR / "resolved_web_sources.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "web_discovery_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "web_source_discovery_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "web_source_discovery_schema.json"

SCHEMA_VERSION = "web_source_discovery_engine_v2"
DRY_RUN_STATUS = "WEB_SOURCE_DISCOVERY_DRY_RUN_REFUSED"
CANDIDATE_STATUS = "WEB_SOURCE_DISCOVERY_CANDIDATE"
PARTIAL_STATUS = "WEB_SOURCE_DISCOVERY_PARTIAL"
REFUSED_STATUS = "WEB_SOURCE_DISCOVERY_REFUSED"

UNSPECIFIED_URL = "UNSPECIFIED"
SOURCE_VERIFICATION_STATUS = "CANDIDATE_WEB_SOURCE_REQUIRES_MANUAL_REVIEW"
RESOLUTION_METHOD_SEED_URL = "seed_candidate_url_metadata_lookup"
RESOLUTION_METHOD_PUBLIC_SEARCH = "public_search_result_metadata_lookup"
RESOLUTION_METHOD_YTDLP_SEARCH = "yt_dlp_search_metadata_lookup"

SUPPORTED_SOURCE_TYPES = (
    "document",
    "parliament_record",
    "video",
    "official_statement",
    "news_article",
    "social_media",
)

REFUSAL_CODES = (
    "REFUSED_WEB_SOURCE_NOT_FOUND",
    "REFUSED_SOURCE_METADATA_UNVERIFIED",
    "REFUSED_WEB_SEARCH_UNAVAILABLE",
    "REFUSED_UNSUPPORTED_SOURCE_TYPE",
    "REFUSED_SEED_VALIDATION_FAILED",
    "REFUSED_NON_PUBLIC_URL",
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

RESOLVED_SOURCE_FIELDS = (
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
    "candidate_topics",
    "expected_claim_keywords",
    "resolution_method",
    "source_verification_status",
    "metadata_hash",
    "resolved_source_root",
    "manual_review_required",
)

REFUSAL_FIELDS = (
    "refusal_id",
    "seed_id",
    "case_id",
    "speaker_name",
    "source_type",
    "platform",
    "candidate_title",
    "candidate_url",
    "refusal_code",
    "refusal_reason",
    "search_query",
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


def _is_real_candidate_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    candidate_url = value.strip()
    return bool(candidate_url) and candidate_url != UNSPECIFIED_URL


def _is_public_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _source_owner_from_url(value: str) -> str:
    parsed = urlparse(value.strip())
    return parsed.netloc.lower()


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source_discovery_only": True,
        "supported_source_types": list(SUPPORTED_SOURCE_TYPES),
        "seed_required_fields": list(SEED_REQUIRED_FIELDS),
        "resolved_source_fields": list(RESOLVED_SOURCE_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "dry_run_behavior": (
            "Dry-run uses validated discovery seeds only, does not access the internet, "
            "resolves no URLs, and refuses every UNSPECIFIED candidate URL."
        ),
        "search_web_behavior": (
            "Search-web may use seed-provided public URLs, optional yt-dlp search for "
            "video seeds, and accessible public search pages. It must not infer or "
            "invent URLs when no supported resolver returns a verifiable public URL."
        ),
        "prohibited_outputs": {
            "quotes_created": 0,
            "timestamps_created": 0,
            "transcript_lines_created": 0,
            "contradictions_created": 0,
            "evidence_approved_count": 0,
        },
        "root_rules": {
            "metadata_hash": "sha256 over deterministic source metadata excluding roots",
            "resolved_source_root": (
                "sha256 over resolved source content excluding resolved_source_root"
            ),
            "refusal_root": "sha256 over refusal content excluding refusal_root",
            "web_source_discovery_engine_root": (
                "sha256 over sorted resolved source roots, sorted refusal roots, and "
                "closed governance flags"
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
        raise ValueError("web_source_discovery_schema schema_version changed unexpectedly")
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
    if seed["source_type"] not in SUPPORTED_SOURCE_TYPES:
        raise ValueError(f"Unsupported source_type: {seed['source_type']}")
    keywords = seed.get("expected_claim_keywords")
    if not isinstance(keywords, list) or not keywords:
        raise ValueError("DiscoverySeed.expected_claim_keywords must be non-empty")
    if not all(isinstance(keyword, str) and keyword.strip() for keyword in keywords):
        raise ValueError("DiscoverySeed.expected_claim_keywords must be non-empty strings")


def _validate_upstream(
    discovery_input: Dict[str, Any],
    validated_payload: Dict[str, Any],
) -> None:
    if not discovery_input:
        raise ValueError("duma_boko_discovery_seeds.json is missing")
    if not validated_payload:
        raise ValueError("validated_discovery_seeds.json is missing")
    input_seeds = discovery_input.get("discovery_seeds")
    validated_seeds = validated_payload.get("discovery_seeds")
    if not isinstance(input_seeds, list) or len(input_seeds) != 60:
        raise ValueError("discovery input must contain 60 discovery seeds")
    if not isinstance(validated_seeds, list) or len(validated_seeds) != 60:
        raise ValueError("validated_discovery_seeds must contain 60 discovery seeds")
    for seed in input_seeds:
        _validate_seed(seed)
    for seed in validated_seeds:
        _validate_seed(seed)
    input_ids = {seed["seed_id"] for seed in input_seeds}
    validated_ids = {seed["seed_id"] for seed in validated_seeds}
    if input_ids != validated_ids:
        raise ValueError("discovery input and validated seed IDs must match")


def _metadata_material(source: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "resolved_source_id": source["resolved_source_id"],
        "seed_id": source["seed_id"],
        "case_id": source["case_id"],
        "speaker_name": source["speaker_name"],
        "source_type": source["source_type"],
        "platform": source["platform"],
        "source_url": source["source_url"],
        "source_title": source["source_title"],
        "source_owner": source["source_owner"],
        "published_date": source["published_date"],
        "candidate_topics": source["candidate_topics"],
        "expected_claim_keywords": source["expected_claim_keywords"],
        "resolution_method": source["resolution_method"],
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
        "refusal_id": f"WEB_REFUSAL_{seed.get('seed_id', 'UNKNOWN')}",
        "seed_id": seed.get("seed_id", ""),
        "case_id": seed.get("case_id", ""),
        "speaker_name": seed.get("speaker_name", ""),
        "source_type": seed.get("source_type", ""),
        "platform": seed.get("platform", ""),
        "candidate_title": seed.get("candidate_title", ""),
        "candidate_url": seed.get("candidate_url", ""),
        "refusal_code": code,
        "refusal_reason": reason,
        "search_query": seed.get("search_query", ""),
        "manual_review_required": True,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def _make_resolved_source(
    seed: Dict[str, Any],
    source_url: str,
    source_title: str,
    source_owner: str,
    published_date: str,
    resolution_method: str,
) -> Dict[str, Any]:
    source = {
        "resolved_source_id": f"WEB_SOURCE_{seed['seed_id']}",
        "seed_id": seed["seed_id"],
        "case_id": seed["case_id"],
        "speaker_name": seed["speaker_name"],
        "source_type": seed["source_type"],
        "platform": seed["platform"],
        "source_url": source_url.strip(),
        "source_title": source_title.strip(),
        "source_owner": source_owner.strip().lower(),
        "published_date": published_date.strip() or "UNVERIFIED_PENDING_MANUAL_REVIEW",
        "candidate_topics": [seed["expected_topic"]],
        "expected_claim_keywords": list(seed["expected_claim_keywords"]),
        "resolution_method": resolution_method,
        "source_verification_status": SOURCE_VERIFICATION_STATUS,
        "metadata_hash": "",
        "resolved_source_root": "",
        "manual_review_required": True,
    }
    source["metadata_hash"] = _hash_json(_metadata_material(source))
    source["resolved_source_root"] = _hash_json(_resolved_root_material(source))
    return source


def _fetch_url_text(url: str) -> Tuple[str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; DumaBokoContradictionEngine/2.0; "
                "source-discovery-only)"
            )
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return "", f"Unsupported content-type for metadata lookup: {content_type}"
            raw = response.read(800000)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return "", f"Unable to fetch URL metadata: {exc}"
    try:
        return raw.decode("utf-8", errors="replace"), ""
    except UnicodeDecodeError as exc:
        return "", f"Unable to decode URL metadata: {exc}"


def _extract_title(page_text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", page_text, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    title = re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()
    return title


def _extract_published_date(page_text: str) -> str:
    patterns = (
        r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']date["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']pubdate["\'][^>]+content=["\']([^"\']+)["\']',
        r'<time[^>]+datetime=["\']([^"\']+)["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            return html.unescape(match.group(1)).strip()
    return "UNVERIFIED_PENDING_MANUAL_REVIEW"


def _metadata_from_public_url(
    seed: Dict[str, Any],
    source_url: str,
    resolution_method: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if not _is_public_url(source_url):
        return None, _make_refusal(
            seed,
            "REFUSED_NON_PUBLIC_URL",
            "Candidate URL is not a public HTTP(S) URL.",
        )
    page_text, error = _fetch_url_text(source_url)
    if error:
        return None, _make_refusal(seed, "REFUSED_SOURCE_METADATA_UNVERIFIED", error)
    title = _extract_title(page_text)
    if not title:
        return None, _make_refusal(
            seed,
            "REFUSED_SOURCE_METADATA_UNVERIFIED",
            "Public URL was reachable, but a non-empty source title could not be verified.",
        )
    source_owner = _source_owner_from_url(source_url)
    source = _make_resolved_source(
        seed,
        source_url,
        title,
        source_owner,
        _extract_published_date(page_text),
        resolution_method,
    )
    return source, None


def _yt_dlp_available() -> bool:
    return shutil.which("yt-dlp") is not None


def _search_video_with_yt_dlp(
    seed: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if seed["source_type"] != "video" or not _yt_dlp_available():
        return None, "yt-dlp is unavailable for video search."
    query = seed["search_query"]
    command = [
        "yt-dlp",
        "--dump-single-json",
        "--skip-download",
        "--no-warnings",
        f"ytsearch1:{query}",
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"yt-dlp video search failed: {exc}"
    if completed.returncode != 0:
        return None, completed.stderr.strip() or "yt-dlp video search returned no result."
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return None, f"yt-dlp returned invalid JSON: {exc}"
    entries = payload.get("entries") if isinstance(payload, dict) else None
    result = entries[0] if isinstance(entries, list) and entries else payload
    if not isinstance(result, dict):
        return None, "yt-dlp video search returned no usable result."
    source_url = result.get("webpage_url") or result.get("original_url") or result.get("url")
    source_title = result.get("title", "")
    if not isinstance(source_url, str) or not _is_public_url(source_url):
        return None, "yt-dlp video search did not return a public source URL."
    if not isinstance(source_title, str) or not source_title.strip():
        return None, "yt-dlp video search did not return a verified title."
    source_owner = result.get("uploader") or _source_owner_from_url(source_url)
    published_date = str(result.get("upload_date") or "UNVERIFIED_PENDING_MANUAL_REVIEW")
    return (
        _make_resolved_source(
            seed,
            source_url,
            source_title,
            str(source_owner),
            published_date,
            RESOLUTION_METHOD_YTDLP_SEARCH,
        ),
        None,
    )


def _duckduckgo_result_url(raw_href: str) -> str:
    href = html.unescape(raw_href)
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        query = parse_qs(parsed.query)
        uddg = query.get("uddg", [""])[0]
        return unquote(uddg)
    return href


def _search_public_page(seed: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    query = quote_plus(seed["search_query"])
    search_url = f"https://duckduckgo.com/html/?q={query}"
    page_text, error = _fetch_url_text(search_url)
    if error:
        return None, error
    links = re.findall(
        r'<a[^>]+class=["\'][^"\']*result__a[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
        page_text,
        flags=re.IGNORECASE,
    )
    for raw_href in links:
        candidate_url = _duckduckgo_result_url(raw_href)
        if _is_public_url(candidate_url):
            return candidate_url, None
    return None, "No public result URL was returned by the accessible search page."


def _resolve_or_refuse_seed(
    seed: Dict[str, Any],
    mode: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    try:
        _validate_seed(seed)
    except ValueError as exc:
        return None, _make_refusal(
            seed,
            "REFUSED_SEED_VALIDATION_FAILED",
            f"Seed validation failed: {exc}",
        )

    if mode == "dry-run":
        return None, _make_refusal(
            seed,
            "REFUSED_WEB_SOURCE_NOT_FOUND",
            "Dry-run does not access the internet and candidate_url is UNSPECIFIED.",
        )

    if _is_real_candidate_url(seed["candidate_url"]):
        return _metadata_from_public_url(
            seed,
            seed["candidate_url"],
            RESOLUTION_METHOD_SEED_URL,
        )

    yt_dlp_source, yt_dlp_error = _search_video_with_yt_dlp(seed)
    if yt_dlp_source is not None:
        return yt_dlp_source, None

    search_result_url, search_error = _search_public_page(seed)
    if search_result_url is None:
        if search_error and (
            "Unable to fetch URL metadata" in search_error
            or "Unsupported content-type" in search_error
        ):
            code = "REFUSED_WEB_SEARCH_UNAVAILABLE"
        else:
            code = "REFUSED_WEB_SOURCE_NOT_FOUND"
        details = search_error or yt_dlp_error or "No supported web resolver returned a URL."
        return None, _make_refusal(seed, code, details)

    source, refusal = _metadata_from_public_url(
        seed,
        search_result_url,
        RESOLUTION_METHOD_PUBLIC_SEARCH,
    )
    if source is not None:
        return source, None
    return None, refusal


def validate_resolved_source(source: Dict[str, Any]) -> None:
    if tuple(source.keys()) != RESOLVED_SOURCE_FIELDS:
        raise ValueError("Resolved web source fields changed unexpectedly")
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
        "resolution_method",
        "source_verification_status",
        "metadata_hash",
        "resolved_source_root",
    ):
        _require_nonempty_string(source, field_name, "ResolvedWebSource")
    if source["source_type"] not in SUPPORTED_SOURCE_TYPES:
        raise ValueError(f"Unsupported resolved source_type: {source['source_type']}")
    if source["source_url"] == UNSPECIFIED_URL or not _is_public_url(source["source_url"]):
        raise ValueError("ResolvedWebSource.source_url must be a public HTTP(S) URL")
    if source["manual_review_required"] is not True:
        raise ValueError("ResolvedWebSource.manual_review_required must be true")
    if source["source_verification_status"] != SOURCE_VERIFICATION_STATUS:
        raise ValueError("ResolvedWebSource.source_verification_status changed")
    if not isinstance(source.get("candidate_topics"), list) or not source["candidate_topics"]:
        raise ValueError("ResolvedWebSource.candidate_topics must be non-empty")
    if (
        not isinstance(source.get("expected_claim_keywords"), list)
        or not source["expected_claim_keywords"]
    ):
        raise ValueError("ResolvedWebSource.expected_claim_keywords must be non-empty")
    if not _is_nonzero_hash(source["metadata_hash"]):
        raise ValueError("ResolvedWebSource.metadata_hash must be non-zero")
    if not _is_nonzero_hash(source["resolved_source_root"]):
        raise ValueError("ResolvedWebSource.resolved_source_root must be non-zero")
    if source["metadata_hash"] != _hash_json(_metadata_material(source)):
        raise ValueError(f"metadata_hash mismatch for {source['resolved_source_id']}")
    if source["resolved_source_root"] != _hash_json(_resolved_root_material(source)):
        raise ValueError(f"resolved_source_root mismatch for {source['resolved_source_id']}")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if tuple(refusal.keys()) != REFUSAL_FIELDS:
        raise ValueError("Web discovery refusal fields changed unexpectedly")
    for field_name in (
        "refusal_id",
        "seed_id",
        "case_id",
        "speaker_name",
        "source_type",
        "platform",
        "candidate_title",
        "candidate_url",
        "refusal_code",
        "refusal_reason",
        "search_query",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "WebDiscoveryRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}")
    if refusal["manual_review_required"] is not True:
        raise ValueError("WebDiscoveryRefusal.manual_review_required must be true")
    if not _is_nonzero_hash(refusal["refusal_root"]):
        raise ValueError("WebDiscoveryRefusal.refusal_root must be non-zero")
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
                    f"  - Source Title: {source['source_title']}",
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
        "# Web Source Discovery Engine v2",
        "",
        "This standalone lane transforms discovery seeds into resolved candidate web "
        "source records or deterministic refusals. It does not extract quotes, "
        "timestamps, transcript lines, approved evidence, or contradiction findings.",
        "",
        "## Summary",
        f"- web_source_discovery_status: {status}",
        f"- mode: {mode}",
        f"- resolved_source_count: {len(resolved_sources)}",
        f"- refusal_count: {len(refusals)}",
        f"- web_source_discovery_engine_root: {engine_root}",
        "",
        "## Resolved Web Sources",
        *resolved_lines,
        "",
        "## Refused Discovery Seeds",
        *refused_lines,
        "",
        "## Downstream Boundary",
        "- Downstream ingestion is intentionally not modified in this lane.",
        "- The future integration lane may consume outputs/web_source_discovery_engine/resolved_web_sources.json.",
        "- Quotes, timestamps, transcript lines, and contradictions remain outside this lane.",
        "",
        "## Guardrails",
        "- Quotes Created: 0",
        "- Timestamps Created: 0",
        "- Transcript Lines Created: 0",
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
    discovery_input: Dict[str, Any],
    validated_payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if mode == "dry-run":
        return list(validated_payload.get("discovery_seeds", []))
    return list(discovery_input.get("discovery_seeds", []))


def build_web_source_discovery_engine(
    mode: str = "dry-run",
    discovery_input_path: Path = DEFAULT_DISCOVERY_INPUT,
    validated_discovery_path: Path = DEFAULT_VALIDATED_DISCOVERY_SEEDS,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "search-web"):
        raise ValueError("mode must be dry-run or search-web")

    discovery_input = _load_json(discovery_input_path)
    validated_payload = _load_json(validated_discovery_path)
    _validate_upstream(discovery_input, validated_payload)
    schema = _schema()
    validate_schema(schema)

    seeds = _seeds_for_mode(mode, discovery_input, validated_payload)
    resolved_sources: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    for seed in seeds:
        resolved, refusal = _resolve_or_refuse_seed(seed, mode)
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
            "transcript_lines_created": 0,
            "contradictions_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        }
    )
    status = _status_for(mode, len(resolved_sources), len(refusals))
    code_counts = {
        "web_source_not_found_refusal_count": sum(
            1 for refusal in refusals if refusal["refusal_code"] == "REFUSED_WEB_SOURCE_NOT_FOUND"
        ),
        "metadata_unverified_refusal_count": sum(
            1
            for refusal in refusals
            if refusal["refusal_code"] == "REFUSED_SOURCE_METADATA_UNVERIFIED"
        ),
        "web_search_unavailable_refusal_count": sum(
            1
            for refusal in refusals
            if refusal["refusal_code"] == "REFUSED_WEB_SEARCH_UNAVAILABLE"
        ),
    }
    schema_hash = _hash_json(schema)
    report = _build_report(status, mode, resolved_sources, refusals, engine_root)
    report_hash = _sha256_text(report)
    summary = {
        "web_source_discovery_status": status,
        "mode": mode,
        "seed_count": len(seeds),
        "resolved_source_count": len(resolved_sources),
        "refusal_count": len(refusals),
        **code_counts,
        "quotes_created": 0,
        "timestamps_created": 0,
        "transcript_lines_created": 0,
        "contradictions_created": 0,
        "evidence_approved_count": 0,
        "resolved_source_roots": resolved_roots,
        "refusal_roots": refusal_roots,
        "web_source_discovery_schema_hash": schema_hash,
        "web_source_discovery_report_hash": report_hash,
        "web_source_discovery_engine_root": engine_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    if not _closed_flags(summary):
        raise ValueError("Web source discovery summary flags must remain closed")

    status_payload = {
        "records": [
            {
                "web_source_discovery_status": status,
                "seed_count": len(seeds),
                "resolved_source_count": len(resolved_sources),
                "refusal_count": len(refusals),
                "web_source_discovery_engine_root": engine_root,
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
    _write_json(RESOLVED_OUTPUT, {"resolved_web_sources": resolved_sources})
    _write_json(REFUSALS_OUTPUT, {"web_discovery_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "payload": status_payload,
        "summary": summary,
        "resolved_web_sources": resolved_sources,
        "web_discovery_refusals": refusals,
        "schema": schema,
        "report": report,
    }
