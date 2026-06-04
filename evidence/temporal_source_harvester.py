#!/usr/bin/env python3
"""
Temporal Source Harvester v2.

Harvests content and metadata only from resolved curated temporal URLs. This
lane never harvests unresolved/refused URLs, invents content, creates quotes,
timestamps, claims, contradictions, production readiness, or approved evidence.
"""

from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse
import hashlib
import html
import http.client
import json
import re
import urllib.error
import urllib.request


DEFAULT_RESOLVED_URLS = Path(
    "outputs/curated_temporal_url_resolution/resolved_temporal_urls.json"
)
DEFAULT_SOURCE_PACK = Path("inputs/temporal_sources/duma_boko_temporal_source_pack.json")
DEFAULT_OUTPUT_DIR = Path("outputs/temporal_source_harvester")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_source_harvester_summary.json"
HARVESTED_OUTPUT = DEFAULT_OUTPUT_DIR / "harvested_temporal_sources.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_source_harvester_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_source_harvester_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_source_harvester_schema.json"

SCHEMA_VERSION = "temporal_source_harvester_v2"
UPSTREAM_SCHEMA_VERSION = "curated_temporal_url_resolution_v2"
UPSTREAM_VERIFICATION_STATUS = "VERIFIED_REACHABLE_CURATED_TEMPORAL_URL"
SOURCE_PACK_VERIFICATION_STATUS = "VERIFIED_REACHABLE_TEMPORAL_SOURCE"

DRY_RUN_STATUS = "TEMPORAL_SOURCE_HARVESTER_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "TEMPORAL_SOURCE_HARVESTER_CANDIDATE"
PARTIAL_STATUS = "TEMPORAL_SOURCE_HARVESTER_PARTIAL"
REFUSED_STATUS = "TEMPORAL_SOURCE_HARVESTER_REFUSED"

UNSPECIFIED = "UNSPECIFIED"
UNAVAILABLE = "UNAVAILABLE"
MAX_FETCH_BYTES = 2_000_000

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

RESOLVED_URL_FIELDS = (
    "resolved_temporal_url_id",
    "source_id",
    "time_direction",
    "source_type",
    "url",
    "title",
    "publisher",
    "published_date",
    "topic",
    "linked_claim_id",
    "http_status",
    "content_type",
    "verification_status",
    "manual_review_required",
    "metadata_hash",
    "resolved_url_root",
)
SOURCE_PACK_FIELDS = (
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
HARVESTED_FIELDS = (
    "harvested_temporal_source_id",
    "source_id",
    "time_direction",
    "source_type",
    "url",
    "title",
    "publisher",
    "published_date",
    "topic",
    "http_status",
    "content_type",
    "content_length",
    "content_sha256",
    "text_excerpt",
    "harvest_method",
    "manual_review_required",
    "metadata_hash",
    "harvest_root",
)
REFUSAL_FIELDS = (
    "refusal_id",
    "source_id",
    "url",
    "refusal_code",
    "refusal_reason",
    "manual_review_required",
    "refusal_root",
)
REFUSAL_CODES = (
    "REFUSED_MALFORMED_RESOLVED_URL",
    "REFUSED_RESOLVED_METADATA_HASH_MISMATCH",
    "REFUSED_RESOLVED_ROOT_MISMATCH",
    "REFUSED_UNSUPPORTED_VERIFICATION_STATUS",
    "REFUSED_DUPLICATE_RESOLVED_SOURCE_ID",
    "REFUSED_MALFORMED_SOURCE_PACK",
    "REFUSED_DUPLICATE_SOURCE_PACK_ID",
    "REFUSED_MISSING_SOURCE_PACK_RECORD",
    "REFUSED_SOURCE_PACK_MISMATCH",
    "REFUSED_SOURCE_PACK_NOT_VERIFIED",
    "REFUSED_FETCH_FAILED",
    "REFUSED_HTTP_STATUS",
    "REFUSED_EMPTY_CONTENT",
    "REFUSED_METADATA_UNVERIFIED",
)


class TemporalHarvestRefusal(ValueError):
    def __init__(self, code: str, reason: str):
        super().__init__(reason)
        self.code = code
        self.reason = reason


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        if tag.lower() in ("script", "style", "noscript"):
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in ("script", "style", "noscript") and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self.parts.append(data)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise TemporalHarvestRefusal(
            "REFUSED_MALFORMED_RESOLVED_URL",
            f"{object_name}.{field_name} must be a non-empty string.",
        )


def _is_public_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _closed_flags(data: Dict[str, Any]) -> bool:
    return (
        data.get("production_ready") is False
        and data.get("approved_evidence") == 0
        and data.get("public_ready") is False
        and data.get("institutional_ready") is False
    )


def _resolved_metadata_material(resolved: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: resolved[field]
        for field in RESOLVED_URL_FIELDS
        if field not in ("metadata_hash", "resolved_url_root")
    }


def _resolved_root_material(resolved: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: resolved[field]
        for field in RESOLVED_URL_FIELDS
        if field != "resolved_url_root"
    }


def _harvested_metadata_material(source: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: source[field]
        for field in HARVESTED_FIELDS
        if field not in ("metadata_hash", "harvest_root")
    }


def _harvest_root_material(source: Dict[str, Any]) -> Dict[str, Any]:
    return {field: source[field] for field in HARVESTED_FIELDS if field != "harvest_root"}


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    return {field: refusal[field] for field in REFUSAL_FIELDS if field != "refusal_root"}


def _validate_resolved_url(resolved: Dict[str, Any]) -> None:
    if not isinstance(resolved, dict) or set(resolved.keys()) != set(RESOLVED_URL_FIELDS):
        raise TemporalHarvestRefusal(
            "REFUSED_MALFORMED_RESOLVED_URL",
            "Resolved temporal URL fields do not match upstream schema.",
        )
    for field_name in RESOLVED_URL_FIELDS:
        if field_name in ("http_status", "manual_review_required"):
            continue
        _require_nonempty_string(resolved, field_name, "ResolvedTemporalUrl")
    if resolved["time_direction"] not in TIME_DIRECTIONS:
        raise TemporalHarvestRefusal(
            "REFUSED_MALFORMED_RESOLVED_URL",
            f"Unsupported time_direction: {resolved['time_direction']}.",
        )
    if resolved["source_type"] not in SOURCE_TYPES:
        raise TemporalHarvestRefusal(
            "REFUSED_MALFORMED_RESOLVED_URL",
            f"Unsupported source_type: {resolved['source_type']}.",
        )
    if not _is_public_url(resolved["url"]):
        raise TemporalHarvestRefusal(
            "REFUSED_MALFORMED_RESOLVED_URL",
            "ResolvedTemporalUrl.url must be public HTTP(S).",
        )
    if resolved["verification_status"] != UPSTREAM_VERIFICATION_STATUS:
        raise TemporalHarvestRefusal(
            "REFUSED_UNSUPPORTED_VERIFICATION_STATUS",
            "ResolvedTemporalUrl.verification_status is not harvestable.",
        )
    if resolved["manual_review_required"] is not True:
        raise TemporalHarvestRefusal(
            "REFUSED_MALFORMED_RESOLVED_URL",
            "ResolvedTemporalUrl.manual_review_required must remain true.",
        )
    if not isinstance(resolved["http_status"], int) or not (200 <= resolved["http_status"] < 400):
        raise TemporalHarvestRefusal(
            "REFUSED_MALFORMED_RESOLVED_URL",
            "ResolvedTemporalUrl.http_status must be 200-399.",
        )
    if resolved["metadata_hash"] != _hash_json(_resolved_metadata_material(resolved)):
        raise TemporalHarvestRefusal(
            "REFUSED_RESOLVED_METADATA_HASH_MISMATCH",
            f"Resolved metadata_hash mismatch for {resolved['source_id']}.",
        )
    if resolved["resolved_url_root"] != _hash_json(_resolved_root_material(resolved)):
        raise TemporalHarvestRefusal(
            "REFUSED_RESOLVED_ROOT_MISMATCH",
            f"Resolved URL root mismatch for {resolved['source_id']}.",
        )


def _load_resolved_urls(resolved_urls_path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(resolved_urls_path)
    if not isinstance(payload, dict):
        raise ValueError("resolved_temporal_urls payload must be a JSON object.")
    if payload.get("schema_version") != UPSTREAM_SCHEMA_VERSION:
        raise ValueError("resolved_temporal_urls schema_version is unsupported.")
    records = payload.get("resolved_temporal_urls")
    if not isinstance(records, list):
        raise ValueError("resolved_temporal_urls must contain a list.")
    seen_source_ids = set()
    for record in records:
        _validate_resolved_url(record)
        source_id = record["source_id"]
        if source_id in seen_source_ids:
            raise TemporalHarvestRefusal(
                "REFUSED_DUPLICATE_RESOLVED_SOURCE_ID",
                f"Duplicate resolved source_id: {source_id}.",
            )
        seen_source_ids.add(source_id)
    return records


def _validate_source_pack_record(source: Dict[str, Any]) -> None:
    if not isinstance(source, dict) or set(source.keys()) != set(SOURCE_PACK_FIELDS):
        raise TemporalHarvestRefusal(
            "REFUSED_MALFORMED_SOURCE_PACK",
            "Curated temporal source pack fields do not match schema.",
        )
    for field_name in SOURCE_PACK_FIELDS:
        if field_name == "manual_review_required":
            continue
        value = source.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise TemporalHarvestRefusal(
                "REFUSED_MALFORMED_SOURCE_PACK",
                f"CuratedTemporalSource.{field_name} must be a non-empty string.",
            )
    if source["time_direction"] not in TIME_DIRECTIONS:
        raise TemporalHarvestRefusal(
            "REFUSED_MALFORMED_SOURCE_PACK",
            f"Unsupported source pack time_direction: {source['time_direction']}.",
        )
    if source["source_type"] not in SOURCE_TYPES:
        raise TemporalHarvestRefusal(
            "REFUSED_MALFORMED_SOURCE_PACK",
            f"Unsupported source pack source_type: {source['source_type']}.",
        )
    if source["manual_review_required"] is not True:
        raise TemporalHarvestRefusal(
            "REFUSED_MALFORMED_SOURCE_PACK",
            "Curated temporal source pack entries must require manual review.",
        )


def _load_source_pack(source_pack_path: Path) -> List[Dict[str, Any]]:
    pack = _load_json(source_pack_path)
    if not isinstance(pack, dict):
        raise ValueError("Curated temporal source pack must be a JSON object.")
    expected_keys = {
        "curated_temporal_sources",
        "generated_by",
        "manual_review_required",
        "pack_scope",
        "pack_version",
        "production_ready",
    }
    if set(pack.keys()) != expected_keys:
        raise ValueError("Curated temporal source pack wrapper keys changed.")
    if pack.get("manual_review_required") is not True:
        raise ValueError("Curated temporal source pack manual_review_required must remain true.")
    if pack.get("production_ready") is not False:
        raise ValueError("Curated temporal source pack production_ready must remain false.")
    sources = pack.get("curated_temporal_sources")
    if not isinstance(sources, list):
        raise ValueError("Curated temporal source pack must contain curated_temporal_sources.")
    seen_source_ids = set()
    for source in sources:
        _validate_source_pack_record(source)
        if source["source_id"] in seen_source_ids:
            raise TemporalHarvestRefusal(
                "REFUSED_DUPLICATE_SOURCE_PACK_ID",
                f"Duplicate source pack source_id: {source['source_id']}.",
            )
        seen_source_ids.add(source["source_id"])
    return sources


def _cross_check_resolved_against_pack(
    resolved_urls: List[Dict[str, Any]], source_pack_records: List[Dict[str, Any]]
) -> None:
    sources_by_id = {source["source_id"]: source for source in source_pack_records}
    for resolved in resolved_urls:
        source = sources_by_id.get(resolved["source_id"])
        if source is None:
            raise TemporalHarvestRefusal(
                "REFUSED_MISSING_SOURCE_PACK_RECORD",
                f"Resolved source_id {resolved['source_id']} is missing from source pack.",
            )
        for field_name in (
            "time_direction",
            "source_type",
            "url",
            "title",
            "publisher",
            "published_date",
            "topic",
            "linked_claim_id",
        ):
            if source[field_name] != resolved[field_name]:
                raise TemporalHarvestRefusal(
                    "REFUSED_SOURCE_PACK_MISMATCH",
                    f"Resolved URL and source pack mismatch for {resolved['source_id']} field {field_name}.",
                )
        if source["verification_status"] != SOURCE_PACK_VERIFICATION_STATUS:
            raise TemporalHarvestRefusal(
                "REFUSED_SOURCE_PACK_NOT_VERIFIED",
                f"Source pack record {resolved['source_id']} is not verified for temporal harvest.",
            )


def _schema_payload() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "upstream_schema_version": UPSTREAM_SCHEMA_VERSION,
        "temporal_source_harvesting_only": True,
        "resolved_url_fields": list(RESOLVED_URL_FIELDS),
        "source_pack_fields": list(SOURCE_PACK_FIELDS),
        "harvested_temporal_source_fields": list(HARVESTED_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "modes": ["dry-run", "harvest"],
        "max_fetch_bytes": MAX_FETCH_BYTES,
        "harvest_methods": [
            "http_get_html_text_excerpt_v1",
            "http_get_plain_text_excerpt_v1",
            "http_get_binary_metadata_v1",
        ],
        "guardrails": {
            "approved_evidence": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "production_ready": False,
            "quotes_created": 0,
            "timestamps_created": 0,
        },
    }


def _normalize_excerpt(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return collapsed[:1000] if collapsed else UNAVAILABLE


def _html_excerpt(content_bytes: bytes) -> str:
    parser = _VisibleTextParser()
    parser.feed(content_bytes.decode("utf-8", errors="replace"))
    return _normalize_excerpt(" ".join(parser.parts))


def _plain_text_excerpt(content_bytes: bytes) -> str:
    return _normalize_excerpt(content_bytes.decode("utf-8", errors="replace"))


def _excerpt_for(content_type: str, content_bytes: bytes) -> Tuple[str, str]:
    lowered = content_type.lower()
    if "text/html" in lowered or "application/xhtml" in lowered:
        return _html_excerpt(content_bytes), "http_get_html_text_excerpt_v1"
    if lowered.startswith("text/") or "application/json" in lowered:
        return _plain_text_excerpt(content_bytes), "http_get_plain_text_excerpt_v1"
    return UNAVAILABLE, "http_get_binary_metadata_v1"


def _fetch_content(url: str) -> Tuple[int, str, bytes]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; DumaBokoContradictionEngine/2.0; "
                "temporal-source-harvester)"
            )
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = int(response.status)
            content_type = response.headers.get("content-type", "")
            content_bytes = response.read(MAX_FETCH_BYTES)
            return status, content_type, content_bytes
    except urllib.error.HTTPError as exc:
        raise TemporalHarvestRefusal(
            "REFUSED_HTTP_STATUS",
            f"HTTP status {int(exc.code)} is outside 200-399.",
        ) from exc
    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
        http.client.HTTPException,
        OSError,
    ) as exc:
        raise TemporalHarvestRefusal("REFUSED_FETCH_FAILED", f"Unable to fetch content: {exc}") from exc


def _make_refusal(
    sequence_number: int, source_id: str, url: str, code: str, reason: str
) -> Dict[str, Any]:
    refusal = {
        "refusal_id": f"TEMPORAL_SOURCE_HARVEST_REFUSAL_{sequence_number:06d}",
        "source_id": source_id,
        "url": url,
        "refusal_code": code,
        "refusal_reason": reason,
        "manual_review_required": True,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Temporal source harvester refusal fields changed unexpectedly.")
    for field_name in REFUSAL_FIELDS:
        if field_name == "manual_review_required":
            continue
        value = refusal.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Temporal source harvester refusal {field_name} must be non-empty.")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("Temporal source harvester refusal manual_review_required must remain true.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['source_id']}.")


def _make_harvested_source(
    sequence_number: int,
    resolved: Dict[str, Any],
    http_status: int,
    content_type: str,
    content_bytes: bytes,
    text_excerpt: str,
    harvest_method: str,
) -> Dict[str, Any]:
    harvested = {
        "harvested_temporal_source_id": f"HARVESTED_TEMPORAL_SOURCE_{sequence_number:06d}",
        "source_id": resolved["source_id"],
        "time_direction": resolved["time_direction"],
        "source_type": resolved["source_type"],
        "url": resolved["url"],
        "title": resolved["title"],
        "publisher": resolved["publisher"],
        "published_date": resolved["published_date"],
        "topic": resolved["topic"],
        "http_status": http_status,
        "content_type": content_type,
        "content_length": len(content_bytes),
        "content_sha256": _sha256_bytes(content_bytes),
        "text_excerpt": text_excerpt,
        "harvest_method": harvest_method,
        "manual_review_required": True,
        "metadata_hash": "",
        "harvest_root": "",
    }
    harvested["metadata_hash"] = _hash_json(_harvested_metadata_material(harvested))
    harvested["harvest_root"] = _hash_json(_harvest_root_material(harvested))
    return harvested


def validate_harvested_source(source: Dict[str, Any]) -> None:
    if set(source.keys()) != set(HARVESTED_FIELDS):
        raise ValueError("Harvested temporal source fields changed unexpectedly.")
    for field_name in HARVESTED_FIELDS:
        if field_name in ("http_status", "content_length", "manual_review_required"):
            continue
        value = source.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"HarvestedTemporalSource.{field_name} must be non-empty.")
    if source["time_direction"] not in TIME_DIRECTIONS:
        raise ValueError("HarvestedTemporalSource.time_direction unsupported.")
    if source["source_type"] not in SOURCE_TYPES:
        raise ValueError("HarvestedTemporalSource.source_type unsupported.")
    if not _is_public_url(source["url"]):
        raise ValueError("HarvestedTemporalSource.url must be public HTTP(S).")
    if not isinstance(source["http_status"], int) or not (200 <= source["http_status"] < 400):
        raise ValueError("HarvestedTemporalSource.http_status must be 200-399.")
    if not isinstance(source["content_length"], int) or source["content_length"] <= 0:
        raise ValueError("HarvestedTemporalSource.content_length must be positive.")
    if source["manual_review_required"] is not True:
        raise ValueError("HarvestedTemporalSource.manual_review_required must remain true.")
    if source["metadata_hash"] != _hash_json(_harvested_metadata_material(source)):
        raise ValueError(f"metadata_hash mismatch for {source['source_id']}.")
    if source["harvest_root"] != _hash_json(_harvest_root_material(source)):
        raise ValueError(f"harvest_root mismatch for {source['source_id']}.")


def _harvest_one(sequence_number: int, resolved: Dict[str, Any]) -> Dict[str, Any]:
    status, content_type, content_bytes = _fetch_content(resolved["url"])
    if status < 200 or status >= 400:
        raise TemporalHarvestRefusal(
            "REFUSED_HTTP_STATUS",
            f"HTTP status {status} is outside 200-399.",
        )
    if not content_type.strip():
        raise TemporalHarvestRefusal(
            "REFUSED_METADATA_UNVERIFIED",
            "Harvested content_type is empty.",
        )
    if not content_bytes:
        raise TemporalHarvestRefusal("REFUSED_EMPTY_CONTENT", "Harvested content bytes are empty.")
    text_excerpt, harvest_method = _excerpt_for(content_type, content_bytes)
    harvested = _make_harvested_source(
        sequence_number,
        resolved,
        status,
        content_type,
        content_bytes,
        text_excerpt,
        harvest_method,
    )
    validate_harvested_source(harvested)
    return harvested


def _build_harvested_and_refusals(
    resolved_urls: List[Dict[str, Any]], mode: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    harvested_sources: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    if mode == "dry-run":
        return harvested_sources, refusals

    for resolved in resolved_urls:
        try:
            harvested_sources.append(_harvest_one(len(harvested_sources) + 1, resolved))
        except TemporalHarvestRefusal as exc:
            refusals.append(
                _make_refusal(
                    len(refusals) + 1,
                    str(resolved.get("source_id") or "UNKNOWN_SOURCE_ID"),
                    str(resolved.get("url") or UNSPECIFIED),
                    exc.code,
                    exc.reason,
                )
            )
    for refusal in refusals:
        validate_refusal(refusal)
    return harvested_sources, refusals


def _status_for(mode: str, harvested_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if harvested_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if harvested_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _summary_root_material(summary: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {
        "temporal_source_harvester_root",
        "temporal_source_harvester_schema_hash",
        "temporal_source_harvester_report_hash",
    }
    return {key: value for key, value in summary.items() if key not in excluded}


def _build_report(
    status: str,
    mode: str,
    resolved_count: int,
    harvested_sources: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    harvested_lines = ["- None"]
    if harvested_sources:
        harvested_lines = []
        for source in harvested_sources[:20]:
            harvested_lines.extend(
                [
                    f"- {source['harvested_temporal_source_id']}: {source['title']}",
                    f"  - Source: {source['source_id']}",
                    f"  - URL: {source['url']}",
                    f"  - Content Length: {source['content_length']}",
                    f"  - Harvest Method: {source['harvest_method']}",
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
                    f"  - URL: {refusal['url']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )

    return "\n".join(
        [
            "# Temporal Source Harvester v2",
            "",
            "This lane harvests content and metadata only from resolved curated "
            "temporal URLs. It does not harvest unresolved/refused URLs, invent "
            "content, create quotes, timestamps, claims, contradictions, "
            "production readiness, or approved evidence.",
            "",
            "## Summary",
            f"- temporal_source_harvester_status: {status}",
            f"- mode: {mode}",
            f"- resolved_url_count: {resolved_count}",
            f"- harvested_temporal_source_count: {len(harvested_sources)}",
            f"- refusal_count: {len(refusals)}",
            f"- temporal_source_harvester_root: {root}",
            "",
            "## First Harvested Temporal Sources",
            *harvested_lines,
            "",
            "## First Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- URLs Invented: 0",
            "- Content Invented: 0",
            "- Quotes Created: 0",
            "- Timestamps Created: 0",
            "- Claims Created: 0",
            "- Contradictions Created: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "",
        ]
    )


def build_temporal_source_harvester(
    mode: str = "dry-run",
    resolved_urls_path: Path = DEFAULT_RESOLVED_URLS,
    source_pack_path: Path = DEFAULT_SOURCE_PACK,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "harvest"):
        raise ValueError("mode must be 'dry-run' or 'harvest'.")

    resolved_urls = _load_resolved_urls(resolved_urls_path)
    source_pack_records = _load_source_pack(source_pack_path)
    _cross_check_resolved_against_pack(resolved_urls, source_pack_records)

    schema = _schema_payload()
    schema_hash = _hash_json(schema)
    harvested_sources, refusals = _build_harvested_and_refusals(resolved_urls, mode)
    status = _status_for(mode, len(harvested_sources), len(refusals))

    summary = {
        "temporal_source_harvester_status": status,
        "mode": mode,
        "resolved_url_count": len(resolved_urls),
        "harvested_temporal_source_count": len(harvested_sources),
        "refusal_count": len(refusals),
        "before_source_count": sum(1 for source in resolved_urls if source["time_direction"] == "BEFORE"),
        "after_source_count": sum(1 for source in resolved_urls if source["time_direction"] == "AFTER"),
        "source_type_counts": {
            source_type: sum(1 for source in resolved_urls if source["source_type"] == source_type)
            for source_type in SOURCE_TYPES
        },
        "source_pack_record_count": len(source_pack_records),
        "source_pack_unresolved_url_count": sum(
            1 for source in source_pack_records if source["url"] == UNSPECIFIED
        ),
        "unresolved_urls_harvested": 0,
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "metadata_hashes": [source["metadata_hash"] for source in harvested_sources],
        "harvest_roots": [source["harvest_root"] for source in harvested_sources],
        "refusal_roots": [refusal["refusal_root"] for refusal in refusals],
        "temporal_source_harvester_schema_hash": schema_hash,
        "temporal_source_harvester_report_hash": "",
        "temporal_source_harvester_root": "",
        "content_invented": 0,
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
    summary["temporal_source_harvester_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(resolved_urls),
        harvested_sources,
        refusals,
        summary["temporal_source_harvester_root"],
    )
    summary["temporal_source_harvester_report_hash"] = _sha256_text(report)
    summary["temporal_source_harvester_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(resolved_urls),
        harvested_sources,
        refusals,
        summary["temporal_source_harvester_root"],
    )
    if not _closed_flags(summary):
        raise ValueError("Temporal source harvester guardrails must remain closed.")

    harvested_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "harvested_temporal_sources": harvested_sources,
    }
    refusals_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "temporal_source_harvester_refusals": refusals,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(output_dir / HARVESTED_OUTPUT.name, harvested_payload)
    _write_json(output_dir / REFUSALS_OUTPUT.name, refusals_payload)
    _write_json(output_dir / SCHEMA_OUTPUT.name, schema)
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    return {
        "summary": summary,
        "harvested_temporal_sources": harvested_sources,
        "temporal_source_harvester_refusals": refusals,
        "schema": schema,
        "report": report,
    }


__all__ = ["build_temporal_source_harvester"]
