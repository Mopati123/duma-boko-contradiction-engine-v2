#!/usr/bin/env python3
"""
Source Harvester Engine v2.

Harvests source metadata only from validated registry source families with real
public base URLs. Dry-run refuses every registry source. This lane does not
create quotes, timestamps, transcripts, claims, approvals, or contradictions.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request


DEFAULT_VALIDATED_REGISTRY = Path(
    "outputs/canonical_source_registry_engine/validated_source_registry.json"
)
DEFAULT_REGISTRY_SUMMARY = Path(
    "outputs/canonical_source_registry_engine/source_registry_summary.json"
)
DEFAULT_REGISTRY_INPUT = Path("inputs/source_registry/duma_boko_source_registry.json")

DEFAULT_OUTPUT_DIR = Path("outputs/source_harvester_engine")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "source_harvester_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "source_harvester_summary.json"
HARVESTED_OUTPUT = DEFAULT_OUTPUT_DIR / "harvested_sources.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "source_harvester_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "source_harvester_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "source_harvester_schema.json"

SCHEMA_VERSION = "source_harvester_engine_v2"
UPSTREAM_STATUS = "CANONICAL_SOURCE_REGISTRY_CANDIDATE"
DRY_RUN_STATUS = "SOURCE_HARVESTER_DRY_RUN_REFUSED"
CANDIDATE_STATUS = "SOURCE_HARVESTER_CANDIDATE"
PARTIAL_STATUS = "SOURCE_HARVESTER_PARTIAL"
REFUSED_STATUS = "SOURCE_HARVESTER_REFUSED"

UNSPECIFIED = "UNSPECIFIED"
HARVEST_STATUS = "CANDIDATE_HARVESTED_SOURCE_REQUIRES_MANUAL_REVIEW"

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
    "registry_source_root",
)

HARVESTED_SOURCE_FIELDS = (
    "harvested_source_id",
    "registry_source_id",
    "source_name",
    "source_category",
    "platform",
    "content_url",
    "content_title",
    "content_owner",
    "published_date",
    "duration",
    "source_type",
    "metadata_method",
    "metadata_hash",
    "harvest_status",
    "manual_review_required",
    "harvested_source_root",
)

REFUSAL_FIELDS = (
    "refusal_id",
    "registry_source_id",
    "source_name",
    "source_category",
    "platform",
    "base_url",
    "refusal_code",
    "refusal_reason",
    "manual_review_required",
    "refusal_root",
)

REFUSAL_CODES = (
    "REFUSED_UNSPECIFIED_BASE_URL",
    "REFUSED_HARVEST_TOOL_UNAVAILABLE",
    "REFUSED_SOURCE_UNREACHABLE",
    "REFUSED_METADATA_UNVERIFIED",
    "REFUSED_UNSUPPORTED_PLATFORM",
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


def _is_real_base_url(value: Any) -> bool:
    return isinstance(value, str) and value.strip() and value.strip() != UNSPECIFIED


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source_harvesting_only": True,
        "upstream_status": UPSTREAM_STATUS,
        "registry_source_fields": list(REGISTRY_SOURCE_FIELDS),
        "harvested_source_fields": list(HARVESTED_SOURCE_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "supported_platforms": list(SUPPORTED_PLATFORMS),
        "dry_run_behavior": "Dry-run refuses every registry source without network access.",
        "harvest_behavior": (
            "Harvest attempts metadata only for real public HTTP(S) base URLs. "
            "It must not create quotes, timestamps, transcripts, claims, or contradictions."
        ),
        "prohibited_outputs": {
            "quotes_created": 0,
            "timestamps_created": 0,
            "transcripts_created": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "evidence_approved_count": 0,
        },
        "root_rules": {
            "metadata_hash": "sha256 over harvested source metadata excluding roots",
            "harvested_source_root": "sha256 over harvested source excluding harvested_source_root",
            "refusal_root": "sha256 over refusal content excluding refusal_root",
            "source_harvester_root": (
                "sha256 over sorted harvested source roots, sorted refusal roots, and closed flags"
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
        raise ValueError("source_harvester_schema schema_version changed unexpectedly")
    if schema.get("harvested_source_fields") != list(HARVESTED_SOURCE_FIELDS):
        raise ValueError("source_harvester_schema harvested_source_fields changed")
    if schema.get("refusal_fields") != list(REFUSAL_FIELDS):
        raise ValueError("source_harvester_schema refusal_fields changed")


def validate_registry_source(source: Dict[str, Any]) -> None:
    if set(source.keys()) != set(REGISTRY_SOURCE_FIELDS):
        raise ValueError("Validated registry source fields changed unexpectedly")
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
        "registry_source_root",
    ):
        _require_nonempty_string(source, field_name, "ValidatedRegistrySource")
    if source["platform"] not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported registry platform: {source['platform']}")
    if source["speaker_focus"] != "Duma Boko":
        raise ValueError("ValidatedRegistrySource.speaker_focus must remain Duma Boko")
    if source["geographic_context"] != "Botswana":
        raise ValueError("ValidatedRegistrySource.geographic_context must remain Botswana")
    if not isinstance(source.get("expected_source_types"), list) or not source["expected_source_types"]:
        raise ValueError("ValidatedRegistrySource.expected_source_types must be non-empty")
    if source["manual_review_required"] is not True:
        raise ValueError("ValidatedRegistrySource.manual_review_required must remain true")
    if not _is_nonzero_hash(source["registry_source_root"]):
        raise ValueError("ValidatedRegistrySource.registry_source_root must be non-zero")


def _validate_upstream(
    validated_payload: Dict[str, Any],
    registry_summary: Dict[str, Any],
    registry_input: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not validated_payload:
        raise ValueError("validated_source_registry.json is missing")
    if not registry_summary:
        raise ValueError("source_registry_summary.json is missing")
    if not registry_input:
        raise ValueError("duma_boko_source_registry.json is missing")
    if registry_summary.get("source_registry_status") != UPSTREAM_STATUS:
        raise ValueError("Canonical source registry status is invalid")
    if registry_summary.get("registry_source_count") != 20:
        raise ValueError("Canonical source registry source count is invalid")
    if registry_summary.get("trust_tier_1_count", 0) < 5:
        raise ValueError("Canonical source registry trust tier count is invalid")
    if registry_summary.get("source_registry_schema_ready") is not True:
        raise ValueError("Canonical source registry schema is not ready")
    for counter in ("quote_count", "timestamp_count", "claim_count", "contradiction_count"):
        if registry_summary.get(counter) != 0:
            raise ValueError(f"Canonical source registry must not create {counter}")
    if not _closed_flags(registry_summary):
        raise ValueError("Canonical source registry guardrails must remain closed")
    if not _is_nonzero_hash(registry_summary.get("source_registry_root")):
        raise ValueError("Canonical source registry root is invalid")
    sources = validated_payload.get("validated_source_registry")
    if not isinstance(sources, list) or len(sources) != registry_summary["registry_source_count"]:
        raise ValueError("validated_source_registry count is invalid")
    for source in sources:
        validate_registry_source(source)
    return sources


def _metadata_material(source: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "harvested_source_id": source["harvested_source_id"],
        "registry_source_id": source["registry_source_id"],
        "source_name": source["source_name"],
        "source_category": source["source_category"],
        "platform": source["platform"],
        "content_url": source["content_url"],
        "content_title": source["content_title"],
        "content_owner": source["content_owner"],
        "published_date": source["published_date"],
        "duration": source["duration"],
        "source_type": source["source_type"],
        "metadata_method": source["metadata_method"],
        "harvest_status": source["harvest_status"],
        "manual_review_required": source["manual_review_required"],
    }


def _harvested_root_material(source: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(source)
    material.pop("harvested_source_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _make_refusal(source: Dict[str, Any], code: str, reason: str) -> Dict[str, Any]:
    refusal = {
        "refusal_id": f"HARVEST_REFUSAL_{source.get('registry_source_id', 'UNKNOWN')}",
        "registry_source_id": source.get("registry_source_id", ""),
        "source_name": source.get("source_name", ""),
        "source_category": source.get("source_category", ""),
        "platform": source.get("platform", ""),
        "base_url": source.get("base_url", ""),
        "refusal_code": code,
        "refusal_reason": reason,
        "manual_review_required": True,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def _fetch_url_text(url: str) -> Tuple[str, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; SourceHarvester/2.0)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return "", f"Unsupported content-type for metadata lookup: {content_type}"
            return response.read(800000).decode("utf-8", errors="replace"), ""
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return "", f"Unable to fetch source metadata: {exc}"


def _extract_title(page_text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", page_text, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()


def _extract_published_date(page_text: str) -> str:
    patterns = (
        r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']date["\'][^>]+content=["\']([^"\']+)["\']',
        r'<time[^>]+datetime=["\']([^"\']+)["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            return html.unescape(match.group(1)).strip()
    return "UNVERIFIED_PENDING_MANUAL_REVIEW"


def _make_harvested_source(
    registry_source: Dict[str, Any],
    content_url: str,
    content_title: str,
    content_owner: str,
    published_date: str,
    duration: str,
    metadata_method: str,
) -> Dict[str, Any]:
    expected_types = registry_source["expected_source_types"]
    source_type = expected_types[0] if expected_types else "document"
    source = {
        "harvested_source_id": f"HARVESTED_{registry_source['registry_source_id']}",
        "registry_source_id": registry_source["registry_source_id"],
        "source_name": registry_source["source_name"],
        "source_category": registry_source["source_category"],
        "platform": registry_source["platform"],
        "content_url": content_url,
        "content_title": content_title,
        "content_owner": content_owner,
        "published_date": published_date or "UNVERIFIED_PENDING_MANUAL_REVIEW",
        "duration": duration or "UNVERIFIED_PENDING_MANUAL_REVIEW",
        "source_type": source_type,
        "metadata_method": metadata_method,
        "metadata_hash": "",
        "harvest_status": HARVEST_STATUS,
        "manual_review_required": True,
        "harvested_source_root": "",
    }
    source["metadata_hash"] = _hash_json(_metadata_material(source))
    source["harvested_source_root"] = _hash_json(_harvested_root_material(source))
    return source


def _harvest_youtube_metadata(source: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if shutil.which("yt-dlp") is None:
        return None, _make_refusal(
            source,
            "REFUSED_HARVEST_TOOL_UNAVAILABLE",
            "yt-dlp is not installed for YouTube metadata harvesting.",
        )
    command = [
        "yt-dlp",
        "--dump-single-json",
        "--skip-download",
        "--no-warnings",
        "--playlist-end",
        "1",
        source["base_url"],
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
        return None, _make_refusal(source, "REFUSED_SOURCE_UNREACHABLE", str(exc))
    if completed.returncode != 0:
        return None, _make_refusal(
            source,
            "REFUSED_SOURCE_UNREACHABLE",
            completed.stderr.strip() or "yt-dlp metadata lookup failed.",
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return None, _make_refusal(source, "REFUSED_METADATA_UNVERIFIED", str(exc))
    entries = payload.get("entries") if isinstance(payload, dict) else None
    item = entries[0] if isinstance(entries, list) and entries else payload
    if not isinstance(item, dict):
        return None, _make_refusal(source, "REFUSED_METADATA_UNVERIFIED", "No usable metadata returned.")
    content_url = item.get("webpage_url") or item.get("original_url") or source["base_url"]
    content_title = item.get("title", "")
    if not isinstance(content_url, str) or not _is_public_url(content_url):
        return None, _make_refusal(source, "REFUSED_METADATA_UNVERIFIED", "No public content URL returned.")
    if not isinstance(content_title, str) or not content_title.strip():
        return None, _make_refusal(source, "REFUSED_METADATA_UNVERIFIED", "No verified content title returned.")
    return (
        _make_harvested_source(
            source,
            content_url,
            content_title.strip(),
            str(item.get("uploader") or urlparse(content_url).netloc.lower()),
            str(item.get("upload_date") or "UNVERIFIED_PENDING_MANUAL_REVIEW"),
            str(item.get("duration") or "UNVERIFIED_PENDING_MANUAL_REVIEW"),
            "yt_dlp_metadata",
        ),
        None,
    )


def _harvest_http_metadata(source: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    page_text, error = _fetch_url_text(source["base_url"])
    if error:
        return None, _make_refusal(source, "REFUSED_SOURCE_UNREACHABLE", error)
    title = _extract_title(page_text)
    if not title:
        return None, _make_refusal(source, "REFUSED_METADATA_UNVERIFIED", "No title metadata found.")
    return (
        _make_harvested_source(
            source,
            source["base_url"],
            title,
            urlparse(source["base_url"]).netloc.lower(),
            _extract_published_date(page_text),
            "UNVERIFIED_PENDING_MANUAL_REVIEW",
            "http_get_html_title",
        ),
        None,
    )


def _harvest_or_refuse_source(
    source: Dict[str, Any],
    mode: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    validate_registry_source(source)
    if mode == "dry-run":
        return None, _make_refusal(
            source,
            "REFUSED_UNSPECIFIED_BASE_URL",
            "Dry-run does not harvest metadata and treats every registry source as unresolved.",
        )
    if source["platform"] not in SUPPORTED_PLATFORMS:
        return None, _make_refusal(source, "REFUSED_UNSUPPORTED_PLATFORM", "Unsupported platform.")
    if not _is_real_base_url(source["base_url"]):
        return None, _make_refusal(
            source,
            "REFUSED_UNSPECIFIED_BASE_URL",
            "Registry source has base_url=UNSPECIFIED.",
        )
    if not _is_public_url(source["base_url"]):
        return None, _make_refusal(
            source,
            "REFUSED_SOURCE_UNREACHABLE",
            "Registry source base_url is not public HTTP(S).",
        )
    if source["platform"] == "youtube":
        return _harvest_youtube_metadata(source)
    return _harvest_http_metadata(source)


def validate_harvested_source(source: Dict[str, Any]) -> None:
    if set(source.keys()) != set(HARVESTED_SOURCE_FIELDS):
        raise ValueError("Harvested source fields changed unexpectedly")
    for field_name in (
        "harvested_source_id",
        "registry_source_id",
        "source_name",
        "source_category",
        "platform",
        "content_url",
        "content_title",
        "content_owner",
        "published_date",
        "duration",
        "source_type",
        "metadata_method",
        "metadata_hash",
        "harvest_status",
        "harvested_source_root",
    ):
        _require_nonempty_string(source, field_name, "HarvestedSource")
    if not _is_public_url(source["content_url"]):
        raise ValueError("HarvestedSource.content_url must be public HTTP(S)")
    if source["manual_review_required"] is not True:
        raise ValueError("HarvestedSource.manual_review_required must remain true")
    if source["harvest_status"] != HARVEST_STATUS:
        raise ValueError("HarvestedSource.harvest_status changed")
    if source["metadata_hash"] != _hash_json(_metadata_material(source)):
        raise ValueError(f"metadata_hash mismatch for {source['harvested_source_id']}")
    if source["harvested_source_root"] != _hash_json(_harvested_root_material(source)):
        raise ValueError(f"harvested_source_root mismatch for {source['harvested_source_id']}")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Source harvester refusal fields changed unexpectedly")
    for field_name in (
        "refusal_id",
        "registry_source_id",
        "source_name",
        "source_category",
        "platform",
        "base_url",
        "refusal_code",
        "refusal_reason",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "SourceHarvesterRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}")
    if refusal["manual_review_required"] is not True:
        raise ValueError("SourceHarvesterRefusal.manual_review_required must remain true")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}")


def _status_for(mode: str, harvested_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if harvested_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if harvested_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _build_report(
    status: str,
    mode: str,
    harvested_sources: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    source_harvester_root: str,
) -> str:
    harvested_lines = ["- None"]
    if harvested_sources:
        harvested_lines = []
        for source in harvested_sources:
            harvested_lines.extend(
                [
                    f"- {source['harvested_source_id']}: {source['content_title']}",
                    f"  - URL: {source['content_url']}",
                    f"  - Manual Review Required: {source['manual_review_required']}",
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
        "# Source Harvester Engine v2",
        "",
        "This lane harvests metadata only. It does not create quotes, timestamps, "
        "transcripts, claims, approvals, or contradictions.",
        "",
        "## Summary",
        f"- source_harvester_status: {status}",
        f"- mode: {mode}",
        f"- harvested_source_count: {len(harvested_sources)}",
        f"- refusal_count: {len(refusals)}",
        f"- source_harvester_root: {source_harvester_root}",
        "",
        "## Harvested Sources",
        *harvested_lines,
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
        "- Evidence Approved Count: 0",
        "- Production Ready: False",
        "- Approved Evidence: 0",
        "- Public Ready: False",
        "- Institutional Ready: False",
        "",
    ]
    return "\n".join(lines)


def build_source_harvester_engine(
    mode: str = "dry-run",
    validated_registry_path: Path = DEFAULT_VALIDATED_REGISTRY,
    registry_summary_path: Path = DEFAULT_REGISTRY_SUMMARY,
    registry_input_path: Path = DEFAULT_REGISTRY_INPUT,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "harvest"):
        raise ValueError("mode must be dry-run or harvest")

    validated_payload = _load_json(validated_registry_path)
    registry_summary = _load_json(registry_summary_path)
    registry_input = _load_json(registry_input_path)
    registry_sources = _validate_upstream(validated_payload, registry_summary, registry_input)
    schema = _schema()
    validate_schema(schema)

    harvested_sources: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    for registry_source in registry_sources:
        harvested, refusal = _harvest_or_refuse_source(registry_source, mode)
        if harvested is not None:
            validate_harvested_source(harvested)
            harvested_sources.append(harvested)
        if refusal is not None:
            validate_refusal(refusal)
            refusals.append(refusal)

    harvested_roots = [source["harvested_source_root"] for source in harvested_sources]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    source_harvester_root = _hash_json(
        {
            "harvested_source_roots": sorted(harvested_roots),
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
    status = _status_for(mode, len(harvested_sources), len(refusals))
    schema_hash = _hash_json(schema)
    report = _build_report(status, mode, harvested_sources, refusals, source_harvester_root)
    report_hash = _sha256_text(report)
    summary = {
        "source_harvester_status": status,
        "mode": mode,
        "registry_source_count": len(registry_sources),
        "harvested_source_count": len(harvested_sources),
        "refusal_count": len(refusals),
        "unspecified_base_url_refusal_count": sum(
            1 for refusal in refusals if refusal["refusal_code"] == "REFUSED_UNSPECIFIED_BASE_URL"
        ),
        "quotes_created": 0,
        "timestamps_created": 0,
        "transcripts_created": 0,
        "claims_created": 0,
        "contradictions_created": 0,
        "evidence_approved_count": 0,
        "source_harvester_schema_ready": True,
        "source_harvester_ready": True,
        "harvested_source_roots": harvested_roots,
        "refusal_roots": refusal_roots,
        "source_harvester_schema_hash": schema_hash,
        "source_harvester_report_hash": report_hash,
        "source_harvester_root": source_harvester_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    if mode == "dry-run" and len(refusals) != len(registry_sources):
        raise ValueError("Dry-run must refuse every registry source")
    if not _closed_flags(summary):
        raise ValueError("Source harvester summary guardrails must remain closed")

    status_payload = {
        "records": [
            {
                "source_harvester_status": status,
                "registry_source_count": len(registry_sources),
                "harvested_source_count": len(harvested_sources),
                "refusal_count": len(refusals),
                "source_harvester_root": source_harvester_root,
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
    _write_json(HARVESTED_OUTPUT, {"harvested_sources": harvested_sources})
    _write_json(REFUSALS_OUTPUT, {"source_harvester_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "payload": status_payload,
        "summary": summary,
        "harvested_sources": harvested_sources,
        "source_harvester_refusals": refusals,
        "schema": schema,
        "report": report,
    }
