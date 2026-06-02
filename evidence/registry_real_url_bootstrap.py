#!/usr/bin/env python3
"""
Registry Real URL Bootstrap Engine v2.

Verifies existing registry base URLs without discovering or inventing
substitute URLs. This lane creates no evidence, videos, quotes, timestamps,
claims, approvals, or contradictions.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
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

DEFAULT_OUTPUT_DIR = Path("outputs/registry_real_url_bootstrap")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "registry_real_url_bootstrap_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "registry_real_url_bootstrap_summary.json"
VERIFIED_OUTPUT = DEFAULT_OUTPUT_DIR / "verified_registry_urls.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "registry_url_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "registry_real_url_bootstrap_report.md"

SCHEMA_VERSION = "registry_real_url_bootstrap_v2"
UPSTREAM_SCHEMA_VERSION = "canonical_source_registry_engine_v2"
UPSTREAM_STATUS = "CANONICAL_SOURCE_REGISTRY_CANDIDATE"

DRY_RUN_STATUS = "REGISTRY_REAL_URL_BOOTSTRAP_DRY_RUN_REFUSED"
CANDIDATE_STATUS = "REGISTRY_REAL_URL_BOOTSTRAP_CANDIDATE"
PARTIAL_STATUS = "REGISTRY_REAL_URL_BOOTSTRAP_PARTIAL"
REFUSED_STATUS = "REGISTRY_REAL_URL_BOOTSTRAP_REFUSED"
APPLY_STATUS = "REGISTRY_REAL_URL_BOOTSTRAP_APPLIED"

UNSPECIFIED = "UNSPECIFIED"
VERIFICATION_STATUS = "VERIFIED_PUBLIC_BASE_URL_REQUIRES_MANUAL_REVIEW"

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

VERIFIED_URL_FIELDS = (
    "verified_url_id",
    "registry_source_id",
    "source_name",
    "source_category",
    "platform",
    "base_url",
    "verified_final_url",
    "verified_title",
    "http_status",
    "content_type",
    "verification_method",
    "verification_status",
    "metadata_hash",
    "url_root",
    "manual_review_required",
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
    "REFUSED_DRY_RUN_NO_NETWORK",
    "REFUSED_NON_PUBLIC_URL",
    "REFUSED_URL_UNREACHABLE",
    "REFUSED_URL_METADATA_UNVERIFIED",
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


def _is_real_base_url(value: Any) -> bool:
    return isinstance(value, str) and value.strip() and value.strip() != UNSPECIFIED


def _is_public_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _metadata_material(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "verified_url_id": record["verified_url_id"],
        "registry_source_id": record["registry_source_id"],
        "source_name": record["source_name"],
        "source_category": record["source_category"],
        "platform": record["platform"],
        "base_url": record["base_url"],
        "verified_final_url": record["verified_final_url"],
        "verified_title": record["verified_title"],
        "http_status": record["http_status"],
        "content_type": record["content_type"],
        "verification_method": record["verification_method"],
        "verification_status": record["verification_status"],
        "manual_review_required": record["manual_review_required"],
    }


def _url_root_material(record: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(record)
    material.pop("url_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _extract_title(page_text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", page_text, re.IGNORECASE | re.DOTALL)
    if not match:
        return "UNVERIFIED_PENDING_MANUAL_REVIEW"
    title = re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()
    return title or "UNVERIFIED_PENDING_MANUAL_REVIEW"


def _make_refusal(source: Dict[str, Any], code: str, reason: str) -> Dict[str, Any]:
    refusal = {
        "refusal_id": f"REGISTRY_URL_REFUSAL_{source.get('registry_source_id', 'UNKNOWN')}",
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


def _make_verified_url(
    source: Dict[str, Any],
    final_url: str,
    title: str,
    http_status: int,
    content_type: str,
    verification_method: str,
) -> Dict[str, Any]:
    record = {
        "verified_url_id": f"VERIFIED_REGISTRY_URL_{source['registry_source_id']}",
        "registry_source_id": source["registry_source_id"],
        "source_name": source["source_name"],
        "source_category": source["source_category"],
        "platform": source["platform"],
        "base_url": source["base_url"].strip(),
        "verified_final_url": final_url.strip(),
        "verified_title": title.strip() or "UNVERIFIED_PENDING_MANUAL_REVIEW",
        "http_status": int(http_status),
        "content_type": content_type.strip() or "UNVERIFIED_PENDING_MANUAL_REVIEW",
        "verification_method": verification_method,
        "verification_status": VERIFICATION_STATUS,
        "metadata_hash": "",
        "url_root": "",
        "manual_review_required": True,
    }
    record["metadata_hash"] = _hash_json(_metadata_material(record))
    record["url_root"] = _hash_json(_url_root_material(record))
    return record


def validate_registry_source(source: Dict[str, Any]) -> None:
    if set(source.keys()) not in (set(REGISTRY_SOURCE_FIELDS), set(VALIDATED_SOURCE_FIELDS)):
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
    if source["speaker_focus"] != "Duma Boko":
        raise ValueError("RegistrySource.speaker_focus must remain Duma Boko")
    if source["geographic_context"] != "Botswana":
        raise ValueError("RegistrySource.geographic_context must remain Botswana")
    if not isinstance(source.get("trust_tier"), int):
        raise ValueError("RegistrySource.trust_tier must be an integer")
    if not isinstance(source.get("expected_source_types"), list) or not source["expected_source_types"]:
        raise ValueError("RegistrySource.expected_source_types must be non-empty")
    if source.get("manual_review_required") is not True:
        raise ValueError("RegistrySource.manual_review_required must remain true")
    if "registry_source_root" in source and not _is_nonzero_hash(source["registry_source_root"]):
        raise ValueError("Validated RegistrySource.registry_source_root must be non-zero")


def _validate_inputs(
    registry_input: Dict[str, Any],
    validated_payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not registry_input:
        raise ValueError("duma_boko_source_registry.json is missing")
    if not validated_payload:
        raise ValueError("validated_source_registry.json is missing")
    if registry_input.get("registry_version") != UPSTREAM_SCHEMA_VERSION:
        raise ValueError("Registry input version is invalid")
    if validated_payload.get("schema_version") != UPSTREAM_SCHEMA_VERSION:
        raise ValueError("Validated source registry schema_version is invalid")
    if validated_payload.get("source_registry_status") != UPSTREAM_STATUS:
        raise ValueError("Validated source registry status is invalid")
    sources = registry_input.get("registry_sources")
    validated_sources = validated_payload.get("validated_source_registry")
    if not isinstance(sources, list) or len(sources) != 20:
        raise ValueError("Registry input must contain 20 sources")
    if not isinstance(validated_sources, list) or len(validated_sources) != 20:
        raise ValueError("Validated registry must contain 20 sources")
    validated_ids = {source["registry_source_id"] for source in validated_sources}
    for source in sources:
        validate_registry_source(source)
        if source["registry_source_id"] not in validated_ids:
            raise ValueError(f"Registry source missing from validated output: {source['registry_source_id']}")
    for source in validated_sources:
        validate_registry_source(source)
    return sources


def _request_url(url: str, method: str) -> Tuple[int, str, str, str]:
    request = urllib.request.Request(
        url,
        method=method,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; RegistryRealUrlBootstrap/2.0; "
                "url-verification-only)"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        final_url = response.geturl()
        content_type = response.headers.get("content-type", "")
        body = ""
        if method == "GET" and ("text/html" in content_type or "application/xhtml" in content_type):
            body = response.read(500000).decode("utf-8", errors="replace")
        return response.status, final_url, content_type, body


def _verify_public_url(source: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    base_url = source["base_url"].strip()
    if not _is_real_base_url(base_url):
        return None, _make_refusal(
            source,
            "REFUSED_UNSPECIFIED_BASE_URL",
            "Registry source has base_url=UNSPECIFIED.",
        )
    if not _is_public_url(base_url):
        return None, _make_refusal(
            source,
            "REFUSED_NON_PUBLIC_URL",
            "Registry source base_url is not a public HTTP(S) URL.",
        )

    last_error = ""
    for method in ("HEAD", "GET"):
        try:
            status, final_url, content_type, body = _request_url(base_url, method)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            last_error = str(exc)
            continue
        if status < 200 or status >= 400:
            last_error = f"HTTP status {status} is not an accepted public success status."
            continue
        if not _is_public_url(final_url):
            return None, _make_refusal(
                source,
                "REFUSED_URL_METADATA_UNVERIFIED",
                "Verified final URL is not public HTTP(S).",
            )
        title = _extract_title(body) if body else "UNVERIFIED_PENDING_MANUAL_REVIEW"
        return _make_verified_url(source, final_url, title, status, content_type, method), None

    return None, _make_refusal(
        source,
        "REFUSED_URL_UNREACHABLE",
        f"Unable to verify registry source base_url: {last_error or 'no response'}",
    )


def _dry_run_refusal(source: Dict[str, Any]) -> Dict[str, Any]:
    if not _is_real_base_url(source["base_url"]):
        return _make_refusal(
            source,
            "REFUSED_UNSPECIFIED_BASE_URL",
            "Dry-run does not verify URLs and registry source has base_url=UNSPECIFIED.",
        )
    return _make_refusal(
        source,
        "REFUSED_DRY_RUN_NO_NETWORK",
        "Dry-run does not perform public URL verification.",
    )


def validate_verified_url(record: Dict[str, Any]) -> None:
    if set(record.keys()) != set(VERIFIED_URL_FIELDS):
        raise ValueError("Verified registry URL fields changed unexpectedly")
    for field_name in (
        "verified_url_id",
        "registry_source_id",
        "source_name",
        "source_category",
        "platform",
        "base_url",
        "verified_final_url",
        "verified_title",
        "content_type",
        "verification_method",
        "verification_status",
        "metadata_hash",
        "url_root",
    ):
        _require_nonempty_string(record, field_name, "VerifiedRegistryUrl")
    if not _is_public_url(record["base_url"]):
        raise ValueError("VerifiedRegistryUrl.base_url must be public HTTP(S)")
    if not _is_public_url(record["verified_final_url"]):
        raise ValueError("VerifiedRegistryUrl.verified_final_url must be public HTTP(S)")
    if not isinstance(record["http_status"], int) or record["http_status"] < 200 or record["http_status"] >= 400:
        raise ValueError("VerifiedRegistryUrl.http_status must be a 2xx/3xx integer")
    if record["manual_review_required"] is not True:
        raise ValueError("VerifiedRegistryUrl.manual_review_required must remain true")
    if record["verification_status"] != VERIFICATION_STATUS:
        raise ValueError("VerifiedRegistryUrl.verification_status changed")
    if record["metadata_hash"] != _hash_json(_metadata_material(record)):
        raise ValueError(f"metadata_hash mismatch for {record['verified_url_id']}")
    if record["url_root"] != _hash_json(_url_root_material(record)):
        raise ValueError(f"url_root mismatch for {record['verified_url_id']}")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Registry URL refusal fields changed unexpectedly")
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
        _require_nonempty_string(refusal, field_name, "RegistryUrlRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}")
    if refusal["manual_review_required"] is not True:
        raise ValueError("RegistryUrlRefusal.manual_review_required must remain true")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}")


def _status_for(mode: str, verified_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if verified_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if verified_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _build_report(
    status: str,
    mode: str,
    verified_urls: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    engine_root: str,
) -> str:
    verified_lines = ["- None"]
    if verified_urls:
        verified_lines = []
        for record in verified_urls:
            verified_lines.extend(
                [
                    f"- {record['verified_url_id']}",
                    f"  - Registry Source ID: {record['registry_source_id']}",
                    f"  - Base URL: {record['base_url']}",
                    f"  - Final URL: {record['verified_final_url']}",
                    f"  - Manual Review Required: {record['manual_review_required']}",
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
        "# Registry Real URL Bootstrap Engine v2",
        "",
        "This lane verifies only existing registry base URLs. It does not search for "
        "replacement URLs, harvest content, extract transcripts, create claims, or "
        "claim contradictions.",
        "",
        "## Summary",
        f"- registry_real_url_bootstrap_status: {status}",
        f"- mode: {mode}",
        f"- verified_url_count: {len(verified_urls)}",
        f"- refusal_count: {len(refusals)}",
        f"- registry_real_url_bootstrap_root: {engine_root}",
        "",
        "## Verified Registry URLs",
        *verified_lines,
        "",
        "## Refusals",
        *refusal_lines,
        "",
        "## Guardrails",
        "- Quotes Created: 0",
        "- Timestamps Created: 0",
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


def _build_outputs(
    mode: str,
    sources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    verified_urls: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    for source in sources:
        validate_registry_source(source)
        if mode == "dry-run":
            refusal = _dry_run_refusal(source)
            validate_refusal(refusal)
            refusals.append(refusal)
            continue
        verified, refusal = _verify_public_url(source)
        if verified is not None:
            validate_verified_url(verified)
            verified_urls.append(verified)
        if refusal is not None:
            validate_refusal(refusal)
            refusals.append(refusal)

    verified_roots = [record["url_root"] for record in verified_urls]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    engine_root = _hash_json(
        {
            "verified_url_roots": sorted(verified_roots),
            "refusal_roots": sorted(refusal_roots),
            "quotes_created": 0,
            "timestamps_created": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        }
    )
    status = _status_for(mode, len(verified_urls), len(refusals))
    report = _build_report(status, mode, verified_urls, refusals, engine_root)
    summary = {
        "registry_real_url_bootstrap_status": status,
        "mode": mode,
        "registry_source_count": len(sources),
        "verified_url_count": len(verified_urls),
        "refusal_count": len(refusals),
        "unspecified_base_url_refusal_count": sum(
            1 for refusal in refusals if refusal["refusal_code"] == "REFUSED_UNSPECIFIED_BASE_URL"
        ),
        "quotes_created": 0,
        "timestamps_created": 0,
        "claims_created": 0,
        "contradictions_created": 0,
        "evidence_approved_count": 0,
        "verified_url_roots": verified_roots,
        "refusal_roots": refusal_roots,
        "registry_real_url_bootstrap_report_hash": _sha256_text(report),
        "registry_real_url_bootstrap_root": engine_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    if not _closed_flags(summary):
        raise ValueError("Registry real URL bootstrap guardrails must remain closed")
    return {
        "status": status,
        "summary": summary,
        "verified_urls": verified_urls,
        "refusals": refusals,
        "report": report,
    }


def _write_outputs(result: Dict[str, Any]) -> None:
    status_payload = {
        "records": [
            {
                "registry_real_url_bootstrap_status": result["status"],
                "registry_source_count": result["summary"]["registry_source_count"],
                "verified_url_count": result["summary"]["verified_url_count"],
                "refusal_count": result["summary"]["refusal_count"],
                "registry_real_url_bootstrap_root": result["summary"][
                    "registry_real_url_bootstrap_root"
                ],
                "production_ready": False,
                "approved_evidence": 0,
                "public_ready": False,
                "institutional_ready": False,
            }
        ]
    }
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(STATUS_OUTPUT, status_payload)
    _write_json(SUMMARY_OUTPUT, result["summary"])
    _write_json(VERIFIED_OUTPUT, {"verified_registry_urls": result["verified_urls"]})
    _write_json(REFUSALS_OUTPUT, {"registry_url_refusals": result["refusals"]})
    _write_text(REPORT_OUTPUT, result["report"])
    result["payload"] = status_payload


def build_registry_real_url_bootstrap(
    mode: str = "dry-run",
    registry_input_path: Path = DEFAULT_REGISTRY_INPUT,
    validated_registry_path: Path = DEFAULT_VALIDATED_REGISTRY,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "verify-public-urls"):
        raise ValueError("mode must be dry-run or verify-public-urls")
    registry_input = _load_json(registry_input_path)
    validated_payload = _load_json(validated_registry_path)
    sources = _validate_inputs(registry_input, validated_payload)
    result = _build_outputs(mode, sources)
    _write_outputs(result)
    return result


def apply_verified_registry_urls(
    registry_input_path: Path = DEFAULT_REGISTRY_INPUT,
    verified_output_path: Path = VERIFIED_OUTPUT,
) -> Dict[str, Any]:
    registry_input = _load_json(registry_input_path)
    verified_payload = _load_json(verified_output_path)
    sources = registry_input.get("registry_sources", [])
    verified_urls = verified_payload.get("verified_registry_urls", [])
    if not isinstance(sources, list) or not isinstance(verified_urls, list):
        raise ValueError("Registry input or verified_registry_urls payload is invalid")
    verified_by_id = {record["registry_source_id"]: record for record in verified_urls}
    applied_count = 0
    for source in sources:
        source_id = source.get("registry_source_id")
        record = verified_by_id.get(source_id)
        if record is None:
            continue
        validate_verified_url(record)
        if source.get("base_url") != record["base_url"]:
            source["base_url"] = record["base_url"]
            applied_count += 1
        if source.get("search_url_template") == UNSPECIFIED:
            source["search_url_template"] = record["base_url"]
    registry_input_path.write_text(
        json.dumps(registry_input, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = {
        "registry_real_url_bootstrap_status": APPLY_STATUS,
        "applied_verified_url_count": applied_count,
        "verified_url_count": len(verified_urls),
        "quotes_created": 0,
        "timestamps_created": 0,
        "claims_created": 0,
        "contradictions_created": 0,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
    }
    return {"summary": summary, "verified_urls": verified_urls}
