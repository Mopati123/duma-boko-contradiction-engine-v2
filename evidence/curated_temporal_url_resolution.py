#!/usr/bin/env python3
"""
Curated Temporal URL Resolution v2.

Resolves only URLs already present in the manually curated temporal source
pack. This lane does not search the web, invent URLs, create quotes,
timestamps, claims, contradictions, production readiness, or approved evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import http.client
import json
import urllib.error
import urllib.request


DEFAULT_INPUT_PACK = Path("inputs/temporal_sources/duma_boko_temporal_source_pack.json")
DEFAULT_VALIDATED_SOURCES = Path(
    "outputs/manually_curated_temporal_source_pack/validated_temporal_sources.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/curated_temporal_url_resolution")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "curated_temporal_url_resolution_summary.json"
RESOLVED_OUTPUT = DEFAULT_OUTPUT_DIR / "resolved_temporal_urls.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "curated_temporal_url_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "curated_temporal_url_resolution_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "curated_temporal_url_resolution_schema.json"

SCHEMA_VERSION = "curated_temporal_url_resolution_v2"
UPSTREAM_SCHEMA_VERSION = "manually_curated_temporal_source_pack_v2"

DRY_RUN_STATUS = "CURATED_TEMPORAL_URL_RESOLUTION_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "CURATED_TEMPORAL_URL_RESOLUTION_CANDIDATE"
PARTIAL_STATUS = "CURATED_TEMPORAL_URL_RESOLUTION_PARTIAL"
REFUSED_STATUS = "CURATED_TEMPORAL_URL_RESOLUTION_REFUSED"

VERIFIED_STATUS = "VERIFIED_REACHABLE_CURATED_TEMPORAL_URL"
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
UPSTREAM_VERIFICATION_STATUSES = (
    "UNVERIFIED_SOURCE_ENTRY",
    "CURATED_TEMPORAL_SOURCE_REQUIRES_MANUAL_REVIEW",
    "VERIFIED_REACHABLE_TEMPORAL_SOURCE",
)

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
UPSTREAM_VALIDATED_SOURCE_FIELDS = (
    *INPUT_SOURCE_FIELDS,
    "metadata_hash",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "curated_source_root",
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
REFUSAL_FIELDS = (
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
REFUSAL_CODES = (
    "REFUSED_UNSPECIFIED_URL",
    "REFUSED_UNREACHABLE",
    "REFUSED_METADATA_UNVERIFIED",
    "REFUSED_SEARCH_RESULT_URL",
    "REFUSED_INPUT_VALIDATION",
)


class UrlResolutionRefusal(ValueError):
    def __init__(self, code: str, reason: str, http_status: int = 0, content_type: str = ""):
        super().__init__(reason)
        self.code = code
        self.reason = reason
        self.http_status = http_status
        self.content_type = content_type


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
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string.")


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
    return False


def _upstream_metadata_material(source: Dict[str, Any]) -> Dict[str, Any]:
    return {field: source[field] for field in INPUT_SOURCE_FIELDS}


def _upstream_root_material(source: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: source[field]
        for field in UPSTREAM_VALIDATED_SOURCE_FIELDS
        if field != "curated_source_root"
    }


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


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    return {field: refusal[field] for field in REFUSAL_FIELDS if field != "refusal_root"}


def _validate_input_source(source: Dict[str, Any]) -> None:
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
    if source["verification_status"] not in UPSTREAM_VERIFICATION_STATUSES:
        raise ValueError(f"Unsupported verification_status: {source['verification_status']}.")
    if source["manual_review_required"] is not True:
        raise ValueError("Curated temporal source entries must require manual review.")


def _validate_upstream_source(source: Dict[str, Any]) -> None:
    if not isinstance(source, dict) or set(source.keys()) != set(UPSTREAM_VALIDATED_SOURCE_FIELDS):
        raise ValueError("Validated temporal source fields do not match upstream schema.")
    _validate_input_source({field: source[field] for field in INPUT_SOURCE_FIELDS})
    if not _closed_flags(source):
        raise ValueError("Validated temporal source guardrails must remain closed.")
    if source["metadata_hash"] != _hash_json(_upstream_metadata_material(source)):
        raise ValueError(f"Upstream metadata_hash mismatch for {source['source_id']}.")
    if source["curated_source_root"] != _hash_json(_upstream_root_material(source)):
        raise ValueError(f"Upstream curated_source_root mismatch for {source['source_id']}.")


def _load_and_validate_inputs(
    input_pack_path: Path, validated_sources_path: Path
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    pack = _load_json(input_pack_path)
    if not isinstance(pack, dict):
        raise ValueError("Curated temporal source pack must be a JSON object.")
    pack_sources = pack.get("curated_temporal_sources")
    if not isinstance(pack_sources, list):
        raise ValueError("Curated temporal source pack must contain curated_temporal_sources list.")
    if pack.get("production_ready") is not False:
        raise ValueError("Curated temporal source pack production_ready must remain false.")
    if pack.get("manual_review_required") is not True:
        raise ValueError("Curated temporal source pack manual_review_required must remain true.")
    for source in pack_sources:
        _validate_input_source(source)

    validated_payload = _load_json(validated_sources_path)
    if not isinstance(validated_payload, dict):
        raise ValueError("Validated temporal sources payload must be a JSON object.")
    if validated_payload.get("schema_version") != UPSTREAM_SCHEMA_VERSION:
        raise ValueError("Validated temporal sources payload schema_version is unsupported.")
    validated_sources = validated_payload.get("validated_temporal_sources")
    if not isinstance(validated_sources, list):
        raise ValueError("Validated temporal sources payload must contain a list.")
    if len(pack_sources) != len(validated_sources):
        raise ValueError("Curated pack and validated temporal sources count mismatch.")

    for index, (pack_source, validated_source) in enumerate(zip(pack_sources, validated_sources), 1):
        _validate_upstream_source(validated_source)
        for field in INPUT_SOURCE_FIELDS:
            if pack_source[field] != validated_source[field]:
                raise ValueError(
                    "Curated pack and validated source mismatch at "
                    f"record {index}, field {field}."
                )
    return pack_sources, validated_sources


def _fetch_url_metadata(url: str, method: str, timeout: int = 12) -> Tuple[int, str, str]:
    request = urllib.request.Request(
        url,
        method=method,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; DumaBokoContradictionEngine/2.0; "
                "curated-temporal-url-resolution-only)"
            )
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), response.geturl(), response.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        content_type = exc.headers.get("content-type", "") if exc.headers else ""
        return int(exc.code), exc.geturl(), content_type
    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
        http.client.HTTPException,
        OSError,
    ) as exc:
        raise UrlResolutionRefusal(
            "REFUSED_UNREACHABLE",
            f"Unable to fetch URL metadata: {exc}",
        ) from exc


def _resolve_public_url(source: Dict[str, Any]) -> Tuple[int, str, str]:
    url = source["url"].strip()
    if not _is_public_url(url):
        raise UrlResolutionRefusal(
            "REFUSED_INPUT_VALIDATION",
            "Curated URL must be UNSPECIFIED or public HTTP(S).",
        )
    if _is_generic_search_url(url):
        raise UrlResolutionRefusal(
            "REFUSED_SEARCH_RESULT_URL",
            "Search-result pages cannot be resolved as temporal URLs.",
        )

    status, resolved_url, content_type = _fetch_url_metadata(url, "HEAD")
    if status in (0, 405, 403) or not content_type:
        status, resolved_url, content_type = _fetch_url_metadata(url, "GET")
    if status < 200 or status >= 400:
        raise UrlResolutionRefusal(
            "REFUSED_UNREACHABLE",
            f"HTTP status {status} is outside 200-399.",
            http_status=status,
            content_type=content_type,
        )
    if not content_type.strip():
        raise UrlResolutionRefusal(
            "REFUSED_METADATA_UNVERIFIED",
            "Resolved URL content_type is empty.",
            http_status=status,
            content_type=content_type,
        )
    if _is_generic_search_url(resolved_url):
        raise UrlResolutionRefusal(
            "REFUSED_SEARCH_RESULT_URL",
            "Resolved URL is a search-result page.",
            http_status=status,
            content_type=content_type,
        )
    return status, resolved_url, content_type


def _make_resolved_source(
    sequence_number: int,
    source: Dict[str, Any],
    http_status: int,
    content_type: str,
) -> Dict[str, Any]:
    resolved = {
        "resolved_temporal_url_id": f"RESOLVED_TEMPORAL_URL_{sequence_number:06d}",
        "source_id": source["source_id"],
        "time_direction": source["time_direction"],
        "source_type": source["source_type"],
        "url": source["url"],
        "title": source["title"],
        "publisher": source["publisher"],
        "published_date": source["published_date"],
        "topic": source["topic"],
        "linked_claim_id": source["linked_claim_id"],
        "http_status": http_status,
        "content_type": content_type,
        "verification_status": VERIFIED_STATUS,
        "manual_review_required": True,
        "metadata_hash": "",
        "resolved_url_root": "",
    }
    resolved["metadata_hash"] = _hash_json(_resolved_metadata_material(resolved))
    resolved["resolved_url_root"] = _hash_json(_resolved_root_material(resolved))
    return resolved


def _make_refusal(
    sequence_number: int,
    source: Dict[str, Any],
    code: str,
    reason: str,
) -> Dict[str, Any]:
    refusal = {
        "refusal_id": f"CURATED_TEMPORAL_URL_REFUSAL_{sequence_number:06d}",
        "source_id": str(source.get("source_id") or "UNKNOWN_SOURCE_ID"),
        "time_direction": str(source.get("time_direction") or "UNSPECIFIED"),
        "source_type": str(source.get("source_type") or "UNSPECIFIED"),
        "url": str(source.get("url") or "UNSPECIFIED"),
        "refusal_code": code,
        "refusal_reason": reason,
        "manual_review_required": True,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_resolved_source(resolved: Dict[str, Any]) -> None:
    if set(resolved.keys()) != set(RESOLVED_URL_FIELDS):
        raise ValueError("Resolved temporal URL fields changed unexpectedly.")
    for field_name in RESOLVED_URL_FIELDS:
        if field_name in ("http_status", "manual_review_required"):
            continue
        _require_nonempty_string(resolved, field_name, "ResolvedTemporalUrl")
    if resolved["time_direction"] not in TIME_DIRECTIONS:
        raise ValueError("ResolvedTemporalUrl.time_direction unsupported.")
    if resolved["source_type"] not in SOURCE_TYPES:
        raise ValueError("ResolvedTemporalUrl.source_type unsupported.")
    if not _is_public_url(resolved["url"]):
        raise ValueError("ResolvedTemporalUrl.url must be public HTTP(S).")
    if _is_generic_search_url(resolved["url"]):
        raise ValueError("ResolvedTemporalUrl.url cannot be a search-result page.")
    if not isinstance(resolved["http_status"], int) or not (200 <= resolved["http_status"] < 400):
        raise ValueError("ResolvedTemporalUrl.http_status must be 200-399.")
    if resolved["verification_status"] != VERIFIED_STATUS:
        raise ValueError("ResolvedTemporalUrl.verification_status unsupported.")
    if resolved["manual_review_required"] is not True:
        raise ValueError("ResolvedTemporalUrl.manual_review_required must remain true.")
    if resolved["metadata_hash"] != _hash_json(_resolved_metadata_material(resolved)):
        raise ValueError(f"metadata_hash mismatch for {resolved['source_id']}.")
    if resolved["resolved_url_root"] != _hash_json(_resolved_root_material(resolved)):
        raise ValueError(f"resolved_url_root mismatch for {resolved['source_id']}.")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Curated temporal URL refusal fields changed unexpectedly.")
    for field_name in REFUSAL_FIELDS:
        if field_name == "manual_review_required":
            continue
        _require_nonempty_string(refusal, field_name, "CuratedTemporalUrlRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError("CuratedTemporalUrlRefusal.refusal_code unsupported.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("CuratedTemporalUrlRefusal.manual_review_required must remain true.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['source_id']}.")


def _build_resolved_and_refusals(
    sources: List[Dict[str, Any]], mode: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    resolved_sources: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []

    if mode == "dry-run":
        return resolved_sources, refusals

    for source in sources:
        try:
            if source["url"] == UNSPECIFIED:
                raise UrlResolutionRefusal(
                    "REFUSED_UNSPECIFIED_URL",
                    "Curated temporal source URL is UNSPECIFIED.",
                )
            http_status, _resolved_url, content_type = _resolve_public_url(source)
            resolved_sources.append(
                _make_resolved_source(
                    len(resolved_sources) + 1,
                    source,
                    http_status,
                    content_type,
                )
            )
        except UrlResolutionRefusal as exc:
            refusals.append(_make_refusal(len(refusals) + 1, source, exc.code, exc.reason))
        except ValueError as exc:
            refusals.append(
                _make_refusal(
                    len(refusals) + 1,
                    source,
                    "REFUSED_INPUT_VALIDATION",
                    str(exc),
                )
            )

    for resolved in resolved_sources:
        validate_resolved_source(resolved)
    for refusal in refusals:
        validate_refusal(refusal)
    return resolved_sources, refusals


def _status_for(mode: str, resolved_count: int, refusal_count: int) -> str:
    if mode == "dry-run" and refusal_count == 0:
        return DRY_RUN_STATUS
    if resolved_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if resolved_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _schema_payload() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "upstream_schema_version": UPSTREAM_SCHEMA_VERSION,
        "resolved_url_fields": list(RESOLVED_URL_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "allowed_time_direction": list(TIME_DIRECTIONS),
        "allowed_source_type": list(SOURCE_TYPES),
        "verified_status": VERIFIED_STATUS,
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
        "curated_temporal_url_resolution_root",
        "curated_temporal_url_resolution_schema_hash",
        "curated_temporal_url_resolution_report_hash",
    }
    return {key: value for key, value in summary.items() if key not in excluded}


def _build_report(
    status: str,
    mode: str,
    temporal_source_count: int,
    resolved_sources: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    resolved_lines = ["- None"]
    if resolved_sources:
        resolved_lines = []
        for resolved in resolved_sources[:20]:
            resolved_lines.extend(
                [
                    f"- {resolved['resolved_temporal_url_id']}",
                    f"  - Source: {resolved['source_id']}",
                    f"  - URL: {resolved['url']}",
                    f"  - HTTP Status: {resolved['http_status']}",
                    f"  - Verification Status: {resolved['verification_status']}",
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
            "# Curated Temporal URL Resolution v2",
            "",
            "This lane resolves only URLs already present in the curated temporal "
            "source pack. It does not search the web, invent URLs, create quotes, "
            "timestamps, claims, contradictions, production readiness, or approved evidence.",
            "",
            "## Summary",
            f"- curated_temporal_url_resolution_status: {status}",
            f"- mode: {mode}",
            f"- temporal_source_count: {temporal_source_count}",
            f"- resolved_url_count: {len(resolved_sources)}",
            f"- refusal_count: {len(refusals)}",
            f"- curated_temporal_url_resolution_root: {root}",
            "",
            "## First Resolved URLs",
            *resolved_lines,
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


def build_curated_temporal_url_resolution(
    mode: str = "dry-run",
    input_pack_path: Path = DEFAULT_INPUT_PACK,
    validated_sources_path: Path = DEFAULT_VALIDATED_SOURCES,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "resolve"):
        raise ValueError("mode must be 'dry-run' or 'resolve'.")

    _pack_sources, validated_sources = _load_and_validate_inputs(
        input_pack_path,
        validated_sources_path,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    resolved_sources, refusals = _build_resolved_and_refusals(validated_sources, mode)
    status = _status_for(mode, len(resolved_sources), len(refusals))
    schema = _schema_payload()
    schema_hash = _hash_json(schema)

    summary = {
        "curated_temporal_url_resolution_status": status,
        "mode": mode,
        "temporal_source_count": len(validated_sources),
        "resolved_url_count": len(resolved_sources),
        "refusal_count": len(refusals),
        "before_source_count": sum(1 for source in validated_sources if source["time_direction"] == "BEFORE"),
        "after_source_count": sum(1 for source in validated_sources if source["time_direction"] == "AFTER"),
        "unspecified_url_count": sum(1 for source in validated_sources if source["url"] == UNSPECIFIED),
        "public_url_count": sum(1 for source in validated_sources if _is_public_url(source["url"])),
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "metadata_hashes": [source["metadata_hash"] for source in resolved_sources],
        "resolved_url_roots": [source["resolved_url_root"] for source in resolved_sources],
        "refusal_roots": [refusal["refusal_root"] for refusal in refusals],
        "curated_temporal_url_resolution_schema_hash": schema_hash,
        "curated_temporal_url_resolution_report_hash": "",
        "curated_temporal_url_resolution_root": "",
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
    summary["curated_temporal_url_resolution_root"] = _hash_json(
        _summary_root_material(summary)
    )
    report = _build_report(
        status,
        mode,
        len(validated_sources),
        resolved_sources,
        refusals,
        summary["curated_temporal_url_resolution_root"],
    )
    summary["curated_temporal_url_resolution_report_hash"] = _sha256_text(report)
    summary["curated_temporal_url_resolution_root"] = _hash_json(
        _summary_root_material(summary)
    )
    report = _build_report(
        status,
        mode,
        len(validated_sources),
        resolved_sources,
        refusals,
        summary["curated_temporal_url_resolution_root"],
    )

    resolved_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "resolved_temporal_urls": resolved_sources,
    }
    refusals_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "curated_temporal_url_refusals": refusals,
    }

    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(output_dir / RESOLVED_OUTPUT.name, resolved_payload)
    _write_json(output_dir / REFUSALS_OUTPUT.name, refusals_payload)
    _write_json(output_dir / SCHEMA_OUTPUT.name, schema)
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    return {
        "summary": summary,
        "resolved_temporal_urls": resolved_sources,
        "curated_temporal_url_refusals": refusals,
        "schema": schema,
        "report": report,
    }


__all__ = ["build_curated_temporal_url_resolution"]
