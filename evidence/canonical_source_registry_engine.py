#!/usr/bin/env python3
"""
Canonical Source Registry Engine v2.

Validates conservative source-family targets for Duma Boko evidence acquisition.
This lane registers where to search; it does not create evidence, URLs, quotes,
timestamps, claims, approvals, or contradictions.
"""

from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_REGISTRY_INPUT = Path("inputs/source_registry/duma_boko_source_registry.json")

DEFAULT_OUTPUT_DIR = Path("outputs/canonical_source_registry_engine")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "source_registry_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "source_registry_summary.json"
VALIDATED_OUTPUT = DEFAULT_OUTPUT_DIR / "validated_source_registry.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "source_registry_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "source_registry_schema.json"

SCHEMA_VERSION = "canonical_source_registry_engine_v2"
REGISTRY_STATUS = "CANONICAL_SOURCE_REGISTRY_CANDIDATE"
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

SUPPORTED_SOURCE_TYPES = (
    "audio",
    "document",
    "news_article",
    "official_statement",
    "parliament_record",
    "social_media",
    "transcript",
    "video",
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


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source_registry_only": True,
        "registry_source_fields": list(REGISTRY_SOURCE_FIELDS),
        "validated_source_fields": list(VALIDATED_SOURCE_FIELDS),
        "source_categories": list(SOURCE_CATEGORIES),
        "supported_source_types": list(SUPPORTED_SOURCE_TYPES),
        "missing_url_rule": {
            "base_url": UNSPECIFIED,
            "search_url_template": UNSPECIFIED,
            "manual_review_required": True,
        },
        "prohibited_outputs": {
            "verified_evidence_count": 0,
            "quote_count": 0,
            "timestamp_count": 0,
            "claim_count": 0,
            "contradiction_count": 0,
            "evidence_approved_count": 0,
        },
        "root_rules": {
            "registry_source_root": "sha256 over each source-family record",
            "source_registry_root": (
                "sha256 over sorted registry source roots, schema hash, and closed flags"
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
        raise ValueError("source_registry_schema schema_version changed unexpectedly")
    if schema.get("registry_source_fields") != list(REGISTRY_SOURCE_FIELDS):
        raise ValueError("source_registry_schema registry_source_fields changed")
    if schema.get("validated_source_fields") != list(VALIDATED_SOURCE_FIELDS):
        raise ValueError("source_registry_schema validated_source_fields changed")
    if schema.get("source_categories") != list(SOURCE_CATEGORIES):
        raise ValueError("source_registry_schema source_categories changed")


def _is_real_url(value: Any) -> bool:
    return isinstance(value, str) and value.strip() and value.strip() != UNSPECIFIED


def validate_registry_source(source: Dict[str, Any]) -> None:
    if set(source.keys()) != set(REGISTRY_SOURCE_FIELDS):
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
    if source["source_category"] not in SOURCE_CATEGORIES:
        raise ValueError(f"Unsupported source_category: {source['source_category']}")
    if source["speaker_focus"] != "Duma Boko":
        raise ValueError("RegistrySource.speaker_focus must remain Duma Boko")
    if source["geographic_context"] != "Botswana":
        raise ValueError("RegistrySource.geographic_context must remain Botswana")
    if not isinstance(source.get("trust_tier"), int) or source["trust_tier"] not in (1, 2, 3, 4):
        raise ValueError("RegistrySource.trust_tier must be an integer from 1 to 4")
    expected_types = source.get("expected_source_types")
    if not isinstance(expected_types, list) or not expected_types:
        raise ValueError("RegistrySource.expected_source_types must be non-empty")
    for source_type in expected_types:
        if source_type not in SUPPORTED_SOURCE_TYPES:
            raise ValueError(f"Unsupported expected source type: {source_type}")
    if (not _is_real_url(source["base_url"]) or not _is_real_url(source["search_url_template"])):
        if source.get("manual_review_required") is not True:
            raise ValueError("Unspecified registry URLs require manual_review_required=true")
    if source.get("manual_review_required") is not True:
        raise ValueError("Initial registry sources must remain manual review required")


def _source_root_material(source: Dict[str, Any]) -> Dict[str, Any]:
    return {field_name: source[field_name] for field_name in REGISTRY_SOURCE_FIELDS}


def _make_validated_source(source: Dict[str, Any]) -> Dict[str, Any]:
    validated = {field_name: source[field_name] for field_name in REGISTRY_SOURCE_FIELDS}
    validated["registry_source_root"] = _hash_json(_source_root_material(validated))
    return validated


def validate_validated_source(source: Dict[str, Any]) -> None:
    if set(source.keys()) != set(VALIDATED_SOURCE_FIELDS):
        raise ValueError("Validated registry source fields changed unexpectedly")
    validate_registry_source({field_name: source[field_name] for field_name in REGISTRY_SOURCE_FIELDS})
    if not _is_nonzero_hash(source["registry_source_root"]):
        raise ValueError("RegistrySource.registry_source_root must be non-zero")
    if source["registry_source_root"] != _hash_json(_source_root_material(source)):
        raise ValueError(f"registry_source_root mismatch for {source['registry_source_id']}")


def _validate_input(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not payload:
        raise ValueError("duma_boko_source_registry.json is missing")
    if payload.get("registry_version") != SCHEMA_VERSION:
        raise ValueError("Source registry version changed unexpectedly")
    if payload.get("speaker_focus") != "Duma Boko":
        raise ValueError("Source registry speaker_focus must remain Duma Boko")
    if payload.get("geographic_context") != "Botswana":
        raise ValueError("Source registry geographic_context must remain Botswana")
    sources = payload.get("registry_sources")
    if not isinstance(sources, list) or len(sources) != 20:
        raise ValueError("Source registry must contain exactly 20 source families")
    source_ids = set()
    categories = set()
    for source in sources:
        validate_registry_source(source)
        source_id = source["registry_source_id"]
        if source_id in source_ids:
            raise ValueError(f"Duplicate registry_source_id: {source_id}")
        source_ids.add(source_id)
        categories.add(source["source_category"])
    missing_categories = set(SOURCE_CATEGORIES) - categories
    if missing_categories:
        raise ValueError(f"Source registry missing categories: {sorted(missing_categories)}")
    return sources


def _build_report(
    validated_sources: List[Dict[str, Any]],
    source_registry_root: str,
) -> str:
    category_lines = []
    for category in SOURCE_CATEGORIES:
        count = sum(1 for source in validated_sources if source["source_category"] == category)
        category_lines.append(f"- {category}: {count}")
    source_lines = []
    for source in validated_sources:
        source_lines.extend(
            [
                f"- {source['registry_source_id']}: {source['source_name']}",
                f"  - Category: {source['source_category']}",
                f"  - Base URL: {source['base_url']}",
                f"  - Manual Review Required: {source['manual_review_required']}",
            ]
        )
    lines = [
        "# Canonical Source Registry Engine v2",
        "",
        "This registry defines conservative source families for future evidence acquisition. "
        "It does not create evidence, verified URLs, quotes, timestamps, claims, "
        "approvals, or contradictions.",
        "",
        "## Summary",
        f"- source_registry_status: {REGISTRY_STATUS}",
        f"- registry_source_count: {len(validated_sources)}",
        f"- source_registry_root: {source_registry_root}",
        "",
        "## Category Counts",
        *category_lines,
        "",
        "## Registry Sources",
        *source_lines,
        "",
        "## Guardrails",
        "- Verified Evidence Count: 0",
        "- Quote Count: 0",
        "- Timestamp Count: 0",
        "- Claim Count: 0",
        "- Contradiction Count: 0",
        "- Evidence Approved Count: 0",
        "- Production Ready: False",
        "- Approved Evidence: 0",
        "- Public Ready: False",
        "- Institutional Ready: False",
        "",
    ]
    return "\n".join(lines)


def build_canonical_source_registry_engine(
    mode: str = "dry-run",
    registry_input_path: Path = DEFAULT_REGISTRY_INPUT,
) -> Dict[str, Any]:
    if mode != "dry-run":
        raise ValueError("Canonical source registry currently supports dry-run only")

    payload = _load_json(registry_input_path)
    registry_sources = _validate_input(payload)
    schema = _schema()
    validate_schema(schema)

    validated_sources = [_make_validated_source(source) for source in registry_sources]
    for source in validated_sources:
        validate_validated_source(source)

    source_roots = [source["registry_source_root"] for source in validated_sources]
    schema_hash = _hash_json(schema)
    source_registry_root = _hash_json(
        {
            "registry_source_roots": sorted(source_roots),
            "source_registry_schema_hash": schema_hash,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        }
    )
    report = _build_report(validated_sources, source_registry_root)
    report_hash = _sha256_text(report)
    trust_tier_1_count = sum(1 for source in validated_sources if source["trust_tier"] == 1)
    manual_review_required_count = sum(
        1 for source in validated_sources if source["manual_review_required"] is True
    )
    summary = {
        "source_registry_status": REGISTRY_STATUS,
        "mode": mode,
        "registry_source_count": len(validated_sources),
        "trust_tier_1_count": trust_tier_1_count,
        "manual_review_required_count": manual_review_required_count,
        "source_registry_schema_ready": True,
        "verified_evidence_count": 0,
        "quote_count": 0,
        "timestamp_count": 0,
        "claim_count": 0,
        "contradiction_count": 0,
        "evidence_approved_count": 0,
        "registry_source_roots": source_roots,
        "source_registry_schema_hash": schema_hash,
        "source_registry_report_hash": report_hash,
        "source_registry_root": source_registry_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    if summary["registry_source_count"] != 20:
        raise ValueError("Registry source count must be exactly 20")
    if summary["trust_tier_1_count"] < 5:
        raise ValueError("Registry requires at least five tier-1 source families")
    if not _closed_flags(summary):
        raise ValueError("Source registry summary guardrails must remain closed")

    status_payload = {
        "records": [
            {
                "source_registry_status": REGISTRY_STATUS,
                "registry_source_count": len(validated_sources),
                "trust_tier_1_count": trust_tier_1_count,
                "source_registry_root": source_registry_root,
                "production_ready": False,
                "approved_evidence": 0,
                "public_ready": False,
                "institutional_ready": False,
            }
        ]
    }
    validated_payload = {
        "schema_version": SCHEMA_VERSION,
        "source_registry_status": REGISTRY_STATUS,
        "validated_source_registry": validated_sources,
        "source_registry_root": source_registry_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
    }

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(STATUS_OUTPUT, status_payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(VALIDATED_OUTPUT, validated_payload)
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "payload": status_payload,
        "summary": summary,
        "validated_source_registry": validated_sources,
        "schema": schema,
        "report": report,
    }
