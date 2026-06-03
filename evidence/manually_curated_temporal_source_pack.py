#!/usr/bin/env python3
"""
Manually Curated Temporal Source Pack v2.

Validates manually curated temporal source records and emits source-pack
candidates only. This lane does not invent URLs, quotes, timestamps, claims,
contradictions, production readiness, or approved evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse
import copy
import hashlib
import json


DEFAULT_INPUT_PACK = Path("inputs/temporal_sources/duma_boko_temporal_source_pack.json")
DEFAULT_OUTPUT_DIR = Path("outputs/manually_curated_temporal_source_pack")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "curated_temporal_source_pack_summary.json"
SOURCES_OUTPUT = DEFAULT_OUTPUT_DIR / "validated_temporal_sources.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "curated_temporal_source_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "curated_temporal_source_pack_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "curated_temporal_source_pack_schema.json"

SCHEMA_VERSION = "manually_curated_temporal_source_pack_v2"
DRY_RUN_STATUS = "CURATED_TEMPORAL_SOURCE_PACK_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "CURATED_TEMPORAL_SOURCE_PACK_CANDIDATE"
PARTIAL_STATUS = "CURATED_TEMPORAL_SOURCE_PACK_PARTIAL"
REFUSED_STATUS = "CURATED_TEMPORAL_SOURCE_PACK_REFUSED"

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
VERIFICATION_STATUSES = (
    "UNVERIFIED_SOURCE_ENTRY",
    "CURATED_TEMPORAL_SOURCE_REQUIRES_MANUAL_REVIEW",
    "VERIFIED_REACHABLE_TEMPORAL_SOURCE",
)
PUBLIC_URL_VERIFICATION_STATUSES = (
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
VALIDATED_SOURCE_FIELDS = (
    *INPUT_SOURCE_FIELDS,
    "metadata_hash",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "curated_source_root",
)
REFUSAL_FIELDS = (
    "curated_temporal_source_refusal_id",
    "source_id",
    "time_direction",
    "source_type",
    "url",
    "refusal_code",
    "refusal_reason",
    "manual_review_required",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "refusal_root",
)
REFUSAL_CODES = (
    "REFUSED_MALFORMED_SOURCE_RECORD",
    "REFUSED_DUPLICATE_SOURCE_ID",
    "REFUSED_UNSUPPORTED_TIME_DIRECTION",
    "REFUSED_UNSUPPORTED_SOURCE_TYPE",
    "REFUSED_UNSUPPORTED_VERIFICATION_STATUS",
    "REFUSED_UNSPECIFIED_URL_GUARDRAIL",
    "REFUSED_PUBLIC_URL_METADATA_INCOMPLETE",
    "REFUSED_SEARCH_RESULT_URL",
)


class SourceValidationError(ValueError):
    def __init__(self, code: str, reason: str):
        super().__init__(reason)
        self.code = code
        self.reason = reason


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
        raise SourceValidationError(
            "REFUSED_MALFORMED_SOURCE_RECORD",
            f"{object_name}.{field_name} must be a non-empty string.",
        )


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


def _source_metadata_material(source: Dict[str, Any]) -> Dict[str, Any]:
    return {field: source[field] for field in INPUT_SOURCE_FIELDS}


def _source_root_material(source: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: source[field]
        for field in VALIDATED_SOURCE_FIELDS
        if field != "curated_source_root"
    }


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    return {field: refusal[field] for field in REFUSAL_FIELDS if field != "refusal_root"}


def _validate_pack_shape(pack: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(pack, dict):
        raise ValueError("Temporal source pack must be a JSON object.")
    sources = pack.get("curated_temporal_sources")
    if not isinstance(sources, list):
        raise ValueError("Temporal source pack must contain curated_temporal_sources list.")
    if pack.get("production_ready") is not False:
        raise ValueError("Temporal source pack production_ready must remain false.")
    if pack.get("manual_review_required") is not True:
        raise ValueError("Temporal source pack manual_review_required must remain true.")
    return sources


def _validate_source_record(source: Dict[str, Any]) -> None:
    if not isinstance(source, dict):
        raise SourceValidationError(
            "REFUSED_MALFORMED_SOURCE_RECORD",
            "Curated temporal source record must be a JSON object.",
        )
    if set(source.keys()) != set(INPUT_SOURCE_FIELDS):
        raise SourceValidationError(
            "REFUSED_MALFORMED_SOURCE_RECORD",
            "Curated temporal source record fields do not match the required schema.",
        )
    for field_name in INPUT_SOURCE_FIELDS:
        if field_name == "manual_review_required":
            continue
        _require_nonempty_string(source, field_name, "CuratedTemporalSource")

    if source["time_direction"] not in TIME_DIRECTIONS:
        raise SourceValidationError(
            "REFUSED_UNSUPPORTED_TIME_DIRECTION",
            f"Unsupported time_direction: {source['time_direction']}.",
        )
    if source["source_type"] not in SOURCE_TYPES:
        raise SourceValidationError(
            "REFUSED_UNSUPPORTED_SOURCE_TYPE",
            f"Unsupported source_type: {source['source_type']}.",
        )
    if source["verification_status"] not in VERIFICATION_STATUSES:
        raise SourceValidationError(
            "REFUSED_UNSUPPORTED_VERIFICATION_STATUS",
            f"Unsupported verification_status: {source['verification_status']}.",
        )
    if source["manual_review_required"] is not True:
        raise SourceValidationError(
            "REFUSED_UNSPECIFIED_URL_GUARDRAIL",
            "Curated temporal source entries must require manual review.",
        )

    url = source["url"].strip()
    if url == "UNSPECIFIED":
        if source["verification_status"] != "UNVERIFIED_SOURCE_ENTRY":
            raise SourceValidationError(
                "REFUSED_UNSPECIFIED_URL_GUARDRAIL",
                "UNSPECIFIED URLs require UNVERIFIED_SOURCE_ENTRY status.",
            )
        return

    if not _is_public_url(url):
        raise SourceValidationError(
            "REFUSED_MALFORMED_SOURCE_RECORD",
            "Curated temporal source URL must be UNSPECIFIED or public HTTP(S).",
        )
    if _is_generic_search_url(url):
        raise SourceValidationError(
            "REFUSED_SEARCH_RESULT_URL",
            "Search-result pages cannot be curated temporal source entries.",
        )
    if source["verification_status"] not in PUBLIC_URL_VERIFICATION_STATUSES:
        raise SourceValidationError(
            "REFUSED_UNSUPPORTED_VERIFICATION_STATUS",
            "Public URL entries require curated manual-review or verified temporal source status.",
        )
    for field_name in ("title", "publisher", "published_date", "topic"):
        if source[field_name].strip() == "UNSPECIFIED":
            raise SourceValidationError(
                "REFUSED_PUBLIC_URL_METADATA_INCOMPLETE",
                f"Public URL entries require non-UNSPECIFIED {field_name}.",
            )


def _make_validated_source(source: Dict[str, Any]) -> Dict[str, Any]:
    validated = copy.deepcopy(source)
    validated["metadata_hash"] = _hash_json(_source_metadata_material(validated))
    validated["production_ready"] = False
    validated["approved_evidence"] = 0
    validated["public_ready"] = False
    validated["institutional_ready"] = False
    validated["curated_source_root"] = _hash_json(_source_root_material(validated))
    return validated


def _source_stub(source: Any) -> Dict[str, Any]:
    if not isinstance(source, dict):
        return {
            "source_id": "UNKNOWN_SOURCE_ID",
            "time_direction": "UNSPECIFIED",
            "source_type": "UNSPECIFIED",
            "url": "UNSPECIFIED",
        }
    return {
        "source_id": str(source.get("source_id") or "UNKNOWN_SOURCE_ID"),
        "time_direction": str(source.get("time_direction") or "UNSPECIFIED"),
        "source_type": str(source.get("source_type") or "UNSPECIFIED"),
        "url": str(source.get("url") or "UNSPECIFIED"),
    }


def _make_refusal(
    sequence_number: int,
    source: Any,
    code: str,
    reason: str,
) -> Dict[str, Any]:
    stub = _source_stub(source)
    refusal = {
        "curated_temporal_source_refusal_id": f"CURATED_TEMPORAL_SOURCE_REFUSAL_{sequence_number:06d}",
        "source_id": stub["source_id"],
        "time_direction": stub["time_direction"],
        "source_type": stub["source_type"],
        "url": stub["url"],
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


def validate_validated_source(source: Dict[str, Any]) -> None:
    if set(source.keys()) != set(VALIDATED_SOURCE_FIELDS):
        raise ValueError("Validated temporal source fields changed unexpectedly.")
    for field_name in VALIDATED_SOURCE_FIELDS:
        if field_name in ("manual_review_required", "production_ready", "approved_evidence", "public_ready", "institutional_ready"):
            continue
        _require_nonempty_string(source, field_name, "ValidatedTemporalSource")
    if source["manual_review_required"] is not True:
        raise ValueError("ValidatedTemporalSource.manual_review_required must remain true.")
    if not _closed_flags(source):
        raise ValueError("ValidatedTemporalSource guardrails must remain closed.")
    _validate_source_record({field: source[field] for field in INPUT_SOURCE_FIELDS})
    if source["metadata_hash"] != _hash_json(_source_metadata_material(source)):
        raise ValueError(f"metadata_hash mismatch for {source['source_id']}.")
    if source["curated_source_root"] != _hash_json(_source_root_material(source)):
        raise ValueError(f"curated_source_root mismatch for {source['source_id']}.")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Curated temporal source refusal fields changed unexpectedly.")
    for field_name in REFUSAL_FIELDS:
        if field_name in ("manual_review_required", "production_ready", "approved_evidence", "public_ready", "institutional_ready"):
            continue
        _require_nonempty_string(refusal, field_name, "CuratedTemporalSourceRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError("CuratedTemporalSourceRefusal.refusal_code unsupported.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("CuratedTemporalSourceRefusal.manual_review_required must remain true.")
    if not _closed_flags(refusal):
        raise ValueError("CuratedTemporalSourceRefusal guardrails must remain closed.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['source_id']}.")


def _build_validated_and_refusals(
    sources: List[Dict[str, Any]], mode: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    validated_sources: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    seen_source_ids = set()
    validatable_source_ids: List[str] = []

    for source in sources:
        try:
            _validate_source_record(source)
            source_id = source["source_id"]
            if source_id in seen_source_ids:
                raise SourceValidationError(
                    "REFUSED_DUPLICATE_SOURCE_ID",
                    f"Duplicate source_id: {source_id}.",
                )
            seen_source_ids.add(source_id)
            validatable_source_ids.append(source_id)
            if mode == "build-pack":
                validated_sources.append(_make_validated_source(source))
        except SourceValidationError as exc:
            refusals.append(_make_refusal(len(refusals) + 1, source, exc.code, exc.reason))

    for source in validated_sources:
        validate_validated_source(source)
    for refusal in refusals:
        validate_refusal(refusal)
    return validated_sources, refusals, validatable_source_ids


def _status_for(mode: str, validated_count: int, refusal_count: int) -> str:
    if mode == "dry-run" and refusal_count == 0:
        return DRY_RUN_STATUS
    if validated_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if validated_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _schema_payload() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "input_source_fields": list(INPUT_SOURCE_FIELDS),
        "validated_source_fields": list(VALIDATED_SOURCE_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "allowed_time_direction": list(TIME_DIRECTIONS),
        "allowed_source_type": list(SOURCE_TYPES),
        "allowed_verification_status": list(VERIFICATION_STATUSES),
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
        "curated_temporal_source_pack_root",
        "curated_temporal_source_pack_schema_hash",
        "curated_temporal_source_pack_report_hash",
    }
    return {key: value for key, value in summary.items() if key not in excluded}


def _build_report(
    status: str,
    mode: str,
    input_count: int,
    validated_sources: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    source_lines = ["- None"]
    if validated_sources:
        source_lines = []
        for source in validated_sources[:20]:
            source_lines.extend(
                [
                    f"- {source['source_id']}",
                    f"  - Direction: {source['time_direction']}",
                    f"  - Type: {source['source_type']}",
                    f"  - URL: {source['url']}",
                    f"  - Verification Status: {source['verification_status']}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['curated_temporal_source_refusal_id']}: {refusal['refusal_code']}",
                    f"  - Source: {refusal['source_id']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Manually Curated Temporal Source Pack v2",
            "",
            "This lane validates manual temporal source records and emits "
            "source-pack candidates only. It does not invent URLs, create "
            "quotes, timestamps, claims, contradictions, production readiness, "
            "or approved evidence.",
            "",
            "## Summary",
            f"- curated_temporal_source_pack_status: {status}",
            f"- mode: {mode}",
            f"- input_source_count: {input_count}",
            f"- temporal_source_count: {len(validated_sources)}",
            f"- refusal_count: {len(refusals)}",
            f"- curated_temporal_source_pack_root: {root}",
            "",
            "## First Validated Sources",
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


def build_manually_curated_temporal_source_pack(
    mode: str = "dry-run",
    input_pack_path: Path = DEFAULT_INPUT_PACK,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "build-pack"):
        raise ValueError("mode must be 'dry-run' or 'build-pack'.")

    pack = _load_json(input_pack_path)
    sources = _validate_pack_shape(pack)
    output_dir.mkdir(parents=True, exist_ok=True)

    validated_sources, refusals, validatable_source_ids = _build_validated_and_refusals(
        sources, mode
    )

    validatable_sources = [
        source
        for source in sources
        if isinstance(source, dict) and source.get("source_id") in set(validatable_source_ids)
    ]
    count_basis = validated_sources if mode == "build-pack" else validatable_sources
    status = _status_for(mode, len(validated_sources), len(refusals))
    schema = _schema_payload()
    schema_hash = _hash_json(schema)

    before_source_count = sum(1 for source in count_basis if source["time_direction"] == "BEFORE")
    after_source_count = sum(1 for source in count_basis if source["time_direction"] == "AFTER")
    unspecified_url_count = sum(1 for source in count_basis if source["url"] == "UNSPECIFIED")
    public_url_count = sum(1 for source in count_basis if _is_public_url(source["url"]))

    summary = {
        "curated_temporal_source_pack_status": status,
        "mode": mode,
        "input_source_count": len(sources),
        "temporal_source_count": len(count_basis),
        "validated_temporal_source_count": len(validated_sources),
        "before_source_count": before_source_count,
        "after_source_count": after_source_count,
        "unspecified_url_count": unspecified_url_count,
        "public_url_count": public_url_count,
        "manual_review_required_count": sum(
            1 for source in count_basis if source["manual_review_required"] is True
        ),
        "refusal_count": len(refusals),
        "metadata_hashes": [source["metadata_hash"] for source in validated_sources],
        "curated_source_roots": [source["curated_source_root"] for source in validated_sources],
        "refusal_roots": [refusal["refusal_root"] for refusal in refusals],
        "curated_temporal_source_pack_schema_hash": schema_hash,
        "curated_temporal_source_pack_report_hash": "",
        "curated_temporal_source_pack_root": "",
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
    summary["curated_temporal_source_pack_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(sources),
        validated_sources,
        refusals,
        summary["curated_temporal_source_pack_root"],
    )
    summary["curated_temporal_source_pack_report_hash"] = _sha256_text(report)
    summary["curated_temporal_source_pack_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(sources),
        validated_sources,
        refusals,
        summary["curated_temporal_source_pack_root"],
    )

    sources_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "validated_temporal_sources": validated_sources,
    }
    refusals_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "curated_temporal_source_refusals": refusals,
    }

    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(output_dir / SOURCES_OUTPUT.name, sources_payload)
    _write_json(output_dir / REFUSALS_OUTPUT.name, refusals_payload)
    _write_json(output_dir / SCHEMA_OUTPUT.name, schema)
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    return {
        "summary": summary,
        "validated_temporal_sources": validated_sources,
        "curated_temporal_source_refusals": refusals,
        "schema": schema,
        "report": report,
    }


__all__ = ["build_manually_curated_temporal_source_pack"]
