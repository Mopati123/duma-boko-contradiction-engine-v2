#!/usr/bin/env python3
"""
Apply Verified Registry Updates v2.

Applies verified registry update candidates to the canonical source registry.
This lane does not harvest content, create transcripts, create quotes, create
claims, create contradictions, approve evidence, or mark production readiness.
"""

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse
import hashlib
import json


DEFAULT_CANDIDATES_INPUT = Path(
    "outputs/registry_discovery_to_bootstrap_bridge/registry_update_candidates.json"
)
DEFAULT_REGISTRY_INPUT = Path("inputs/source_registry/duma_boko_source_registry.json")

DEFAULT_OUTPUT_DIR = Path("outputs/apply_verified_registry_updates")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "apply_registry_updates_summary.json"
APPLIED_OUTPUT = DEFAULT_OUTPUT_DIR / "applied_registry_updates.json"
PREVIEW_OUTPUT = DEFAULT_OUTPUT_DIR / "updated_source_registry_preview.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "apply_registry_updates_report.md"

SCHEMA_VERSION = "apply_verified_registry_updates_v2"
UPSTREAM_REGISTRY_SCHEMA_VERSION = "canonical_source_registry_engine_v2"
UPSTREAM_CANDIDATE_STATUS = "REGISTRY_UPDATE_CANDIDATE"

DRY_RUN_STATUS = "APPLY_VERIFIED_REGISTRY_UPDATES_DRY_RUN_PREVIEW"
APPLIED_STATUS = "APPLY_VERIFIED_REGISTRY_UPDATES_APPLIED"
SOURCE_ORIGIN = "registry_discovery_to_bootstrap_bridge"
REGISTRY_VERIFICATION_STATUS = "VERIFIED_REACHABLE_PUBLIC_ENDPOINT"
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

REGISTRY_UPDATE_CANDIDATE_FIELDS = (
    "registry_update_candidate_id",
    "promoted_endpoint_id",
    "source_name",
    "source_category",
    "platform",
    "base_url",
    "resolved_url",
    "http_status",
    "content_type",
    "trust_tier",
    "manual_review_required",
    "source_origin",
    "candidate_status",
    "metadata_hash",
    "registry_update_candidate_root",
)

APPLIED_UPDATE_FIELDS = (
    "applied_update_id",
    "registry_update_candidate_id",
    "promoted_endpoint_id",
    "registry_source_id",
    "source_name",
    "source_category",
    "platform",
    "base_url",
    "resolved_url",
    "http_status",
    "content_type",
    "trust_tier",
    "manual_review_required",
    "verification_status",
    "source_origin",
    "apply_status",
    "metadata_hash",
    "applied_update_root",
)

REFUSAL_FIELDS = (
    "refusal_id",
    "registry_update_candidate_id",
    "promoted_endpoint_id",
    "candidate_url",
    "refusal_code",
    "refusal_reason",
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


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string")


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


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
    if host.endswith("twitter.com") and path.startswith("/search"):
        return True
    if host.endswith("x.com") and path.startswith("/search"):
        return True
    return False


def _closed_flags(data: Dict[str, Any]) -> bool:
    return (
        data.get("production_ready") is False
        and data.get("approved_evidence") == 0
        and data.get("public_ready") is False
        and data.get("institutional_ready") is False
    )


def _registry_source_key(source: Dict[str, Any]) -> Tuple[str, str, str, int]:
    return (
        source["source_name"],
        source["source_category"],
        source["platform"],
        int(source["trust_tier"]),
    )


def _candidate_key(candidate: Dict[str, Any]) -> Tuple[str, str, str, int]:
    return (
        candidate["source_name"],
        candidate["source_category"],
        candidate["platform"],
        int(candidate["trust_tier"]),
    )


def _applied_update_root_material(update: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(update)
    material.pop("applied_update_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def validate_registry_source(source: Dict[str, Any]) -> None:
    required_fields = set(REGISTRY_SOURCE_FIELDS)
    optional_fields = {"resolved_url", "verification_status", "source_origin", "verified_endpoints"}
    source_fields = set(source.keys())
    if not required_fields <= source_fields or source_fields - required_fields - optional_fields:
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
    if source["platform"] not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported platform: {source['platform']}")
    if source["speaker_focus"] != "Duma Boko":
        raise ValueError("RegistrySource.speaker_focus must remain Duma Boko")
    if source["geographic_context"] != "Botswana":
        raise ValueError("RegistrySource.geographic_context must remain Botswana")
    if not isinstance(source.get("trust_tier"), int) or source["trust_tier"] not in (1, 2, 3, 4):
        raise ValueError("RegistrySource.trust_tier must be an integer from 1 to 4")
    if source["manual_review_required"] is not True:
        raise ValueError("RegistrySource.manual_review_required must remain true")


def validate_registry_update_candidate(candidate: Dict[str, Any]) -> str:
    if set(candidate.keys()) != set(REGISTRY_UPDATE_CANDIDATE_FIELDS):
        return "Registry update candidate fields changed unexpectedly."
    for field_name in (
        "registry_update_candidate_id",
        "promoted_endpoint_id",
        "source_name",
        "source_category",
        "platform",
        "base_url",
        "resolved_url",
        "content_type",
        "source_origin",
        "candidate_status",
        "metadata_hash",
        "registry_update_candidate_root",
    ):
        value = candidate.get(field_name)
        if not isinstance(value, str) or not value.strip():
            return f"RegistryUpdateCandidate.{field_name} must be a non-empty string."
    if candidate["source_category"] not in SOURCE_CATEGORIES:
        return f"Unsupported source_category: {candidate['source_category']}."
    if candidate["platform"] not in SUPPORTED_PLATFORMS:
        return f"Unsupported platform: {candidate['platform']}."
    if candidate["candidate_status"] != UPSTREAM_CANDIDATE_STATUS:
        return "Candidate status is not a registry update candidate."
    if not isinstance(candidate["http_status"], int) or candidate["http_status"] < 200 or candidate["http_status"] >= 400:
        return "Candidate http_status must be 200-399."
    if not isinstance(candidate["trust_tier"], int) or candidate["trust_tier"] not in (1, 2, 3, 4):
        return "Candidate trust_tier must be 1-4."
    if candidate["manual_review_required"] is not True:
        return "Candidate manual_review_required must remain true."
    if candidate["source_origin"] != "manual_review_endpoint_promotion_engine":
        return "Candidate source_origin is not the endpoint promotion bridge input."
    if not _is_nonzero_hash(candidate["metadata_hash"]):
        return "Candidate metadata_hash must be non-empty."
    if not _is_public_url(candidate["base_url"]) or not _is_public_url(candidate["resolved_url"]):
        return "Candidate URLs must be public HTTP(S)."
    if _is_generic_search_url(candidate["base_url"]) or _is_generic_search_url(candidate["resolved_url"]):
        return "Search endpoints must not be applied to the canonical registry."
    return ""


def _make_refusal(
    sequence_number: int,
    candidate: Dict[str, Any],
    refusal_code: str,
    refusal_reason: str,
) -> Dict[str, Any]:
    refusal = {
        "refusal_id": f"APPLY_REGISTRY_UPDATE_REFUSAL_{sequence_number:03d}",
        "registry_update_candidate_id": candidate.get("registry_update_candidate_id", UNSPECIFIED),
        "promoted_endpoint_id": candidate.get("promoted_endpoint_id", UNSPECIFIED),
        "candidate_url": candidate.get("resolved_url") or candidate.get("base_url") or UNSPECIFIED,
        "refusal_code": refusal_code,
        "refusal_reason": refusal_reason,
        "manual_review_required": True,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Apply registry update refusal fields changed unexpectedly")
    for field_name in (
        "refusal_id",
        "registry_update_candidate_id",
        "promoted_endpoint_id",
        "candidate_url",
        "refusal_code",
        "refusal_reason",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "ApplyRegistryUpdateRefusal")
    if not refusal["refusal_code"].startswith("REFUSED_"):
        raise ValueError("Apply registry update refusal code must start with REFUSED_")
    if refusal["manual_review_required"] is not True:
        raise ValueError("ApplyRegistryUpdateRefusal.manual_review_required must remain true")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}")


def _make_applied_update(
    sequence_number: int,
    candidate: Dict[str, Any],
    registry_source: Dict[str, Any],
    apply_status: str,
) -> Dict[str, Any]:
    update = {
        "applied_update_id": f"APPLIED_REGISTRY_UPDATE_{sequence_number:03d}",
        "registry_update_candidate_id": candidate["registry_update_candidate_id"],
        "promoted_endpoint_id": candidate["promoted_endpoint_id"],
        "registry_source_id": registry_source["registry_source_id"],
        "source_name": candidate["source_name"],
        "source_category": candidate["source_category"],
        "platform": candidate["platform"],
        "base_url": candidate["base_url"],
        "resolved_url": candidate["resolved_url"],
        "http_status": candidate["http_status"],
        "content_type": candidate["content_type"],
        "trust_tier": candidate["trust_tier"],
        "manual_review_required": True,
        "verification_status": REGISTRY_VERIFICATION_STATUS,
        "source_origin": SOURCE_ORIGIN,
        "apply_status": apply_status,
        "metadata_hash": candidate["metadata_hash"],
        "applied_update_root": "",
    }
    update["applied_update_root"] = _hash_json(_applied_update_root_material(update))
    return update


def validate_applied_update(update: Dict[str, Any]) -> None:
    if set(update.keys()) != set(APPLIED_UPDATE_FIELDS):
        raise ValueError("Applied registry update fields changed unexpectedly")
    for field_name in (
        "applied_update_id",
        "registry_update_candidate_id",
        "promoted_endpoint_id",
        "registry_source_id",
        "source_name",
        "source_category",
        "platform",
        "base_url",
        "resolved_url",
        "content_type",
        "verification_status",
        "source_origin",
        "apply_status",
        "metadata_hash",
        "applied_update_root",
    ):
        _require_nonempty_string(update, field_name, "AppliedRegistryUpdate")
    if not _is_public_url(update["base_url"]) or not _is_public_url(update["resolved_url"]):
        raise ValueError("AppliedRegistryUpdate URLs must be public HTTP(S)")
    if _is_generic_search_url(update["base_url"]) or _is_generic_search_url(update["resolved_url"]):
        raise ValueError("AppliedRegistryUpdate must not point at a search endpoint")
    if update["verification_status"] != REGISTRY_VERIFICATION_STATUS:
        raise ValueError("AppliedRegistryUpdate.verification_status changed")
    if update["source_origin"] != SOURCE_ORIGIN:
        raise ValueError("AppliedRegistryUpdate.source_origin changed")
    if update["manual_review_required"] is not True:
        raise ValueError("AppliedRegistryUpdate.manual_review_required must remain true")
    if not isinstance(update["http_status"], int) or update["http_status"] < 200 or update["http_status"] >= 400:
        raise ValueError("AppliedRegistryUpdate.http_status must be 200-399")
    if not isinstance(update["trust_tier"], int) or update["trust_tier"] not in (1, 2, 3, 4):
        raise ValueError("AppliedRegistryUpdate.trust_tier must be 1-4")
    if update["applied_update_root"] != _hash_json(_applied_update_root_material(update)):
        raise ValueError(f"applied_update_root mismatch for {update['applied_update_id']}")


def _validate_upstream(
    candidates_payload: Dict[str, Any],
    registry_input: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not candidates_payload:
        raise ValueError("registry_update_candidates output is missing")
    if not registry_input:
        raise ValueError("source registry input is missing")
    if registry_input.get("registry_version") != UPSTREAM_REGISTRY_SCHEMA_VERSION:
        raise ValueError("source registry input version is invalid")
    candidates = candidates_payload.get("registry_update_candidates")
    registry_sources = registry_input.get("registry_sources")
    if not isinstance(candidates, list):
        raise ValueError("registry_update_candidates must be a list")
    if not isinstance(registry_sources, list) or len(registry_sources) != 20:
        raise ValueError("source registry input must contain 20 source families")
    for source in registry_sources:
        validate_registry_source(source)
    return candidates, registry_sources


def _embed_endpoint(candidate: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "registry_update_candidate_id": candidate["registry_update_candidate_id"],
        "promoted_endpoint_id": candidate["promoted_endpoint_id"],
        "base_url": candidate["base_url"],
        "resolved_url": candidate["resolved_url"],
        "http_status": candidate["http_status"],
        "content_type": candidate["content_type"],
        "metadata_hash": candidate["metadata_hash"],
        "verification_status": REGISTRY_VERIFICATION_STATUS,
        "source_origin": SOURCE_ORIGIN,
        "manual_review_required": True,
    }


def _apply_updates_to_registry(
    registry_input: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    mode: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], int]:
    updated_registry = deepcopy(registry_input)
    registry_sources = updated_registry["registry_sources"]
    source_by_key: Dict[Tuple[str, str, str, int], Dict[str, Any]] = {}
    for source in registry_sources:
        key = _registry_source_key(source)
        if key in source_by_key:
            raise ValueError(f"Duplicate registry source tuple: {key}")
        source_by_key[key] = source

    apply_status = "APPLY_REGISTRY_UPDATE_PREVIEW" if mode == "dry-run" else "APPLY_REGISTRY_UPDATE_APPLIED"
    accepted_updates: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    source_ids_touched = set()
    for candidate in candidates:
        validation_error = validate_registry_update_candidate(candidate)
        source = source_by_key.get(_candidate_key(candidate)) if not validation_error else None
        if source is None and not validation_error:
            validation_error = "No matching source family found in canonical registry."
        if validation_error:
            refusal = _make_refusal(
                len(refusals) + 1,
                candidate,
                "REFUSED_REGISTRY_UPDATE_NOT_APPLIED",
                validation_error,
            )
            validate_refusal(refusal)
            refusals.append(refusal)
            continue

        update = _make_applied_update(len(accepted_updates) + 1, candidate, source, apply_status)
        validate_applied_update(update)
        accepted_updates.append(update)
        source_ids_touched.add(source["registry_source_id"])

        if mode != "apply":
            continue

        endpoints = source.setdefault("verified_endpoints", [])
        if not isinstance(endpoints, list):
            raise ValueError(f"{source['registry_source_id']} verified_endpoints must be a list")
        existing_candidate_ids = {
            endpoint.get("registry_update_candidate_id")
            for endpoint in endpoints
            if isinstance(endpoint, dict)
        }
        if candidate["registry_update_candidate_id"] not in existing_candidate_ids:
            endpoints.append(_embed_endpoint(candidate))
        if "resolved_url" not in source:
            source["base_url"] = candidate["base_url"]
            source["resolved_url"] = candidate["resolved_url"]
        source["manual_review_required"] = True
        source["verification_status"] = REGISTRY_VERIFICATION_STATUS
        source["source_origin"] = SOURCE_ORIGIN

    return updated_registry, accepted_updates, refusals, len(source_ids_touched)


def _build_report(
    status: str,
    mode: str,
    updates: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    source_family_update_count: int,
    engine_root: str,
) -> str:
    update_lines = ["- None"]
    if updates:
        update_lines = []
        for update in updates[:40]:
            update_lines.extend(
                [
                    f"- {update['applied_update_id']}",
                    f"  - Registry Source ID: {update['registry_source_id']}",
                    f"  - Candidate: {update['registry_update_candidate_id']}",
                    f"  - Base URL: {update['base_url']}",
                    f"  - Resolved URL: {update['resolved_url']}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:40]:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Candidate URL: {refusal['candidate_url']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Apply Verified Registry Updates v2",
            "",
            "This lane applies verified registry update candidates to the source registry. "
            "It does not harvest content, create transcripts, create quotes, create claims, "
            "or create contradictions.",
            "",
            "## Summary",
            f"- apply_registry_updates_status: {status}",
            f"- mode: {mode}",
            f"- registry_update_candidate_count: {len(updates) + len(refusals)}",
            f"- accepted_update_count: {len(updates)}",
            f"- source_family_update_count: {source_family_update_count}",
            f"- refusal_count: {len(refusals)}",
            f"- apply_registry_updates_root: {engine_root}",
            "",
            "## Applied Updates",
            *update_lines,
            "",
            "## Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- Search Endpoints Applied: 0",
            "- Quotes Created: 0",
            "- Timestamps Created: 0",
            "- Transcripts Created: 0",
            "- Claims Created: 0",
            "- Contradictions Created: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "- Public Ready: False",
            "- Institutional Ready: False",
            "",
        ]
    )


def build_apply_verified_registry_updates(
    mode: str = "dry-run",
    candidates_input_path: Path = DEFAULT_CANDIDATES_INPUT,
    registry_input_path: Path = DEFAULT_REGISTRY_INPUT,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "apply"):
        raise ValueError("mode must be dry-run or apply")
    candidates_payload = _load_json(candidates_input_path)
    registry_input = _load_json(registry_input_path)
    candidates, _registry_sources = _validate_upstream(candidates_payload, registry_input)
    updated_registry, accepted_updates, refusals, source_family_update_count = _apply_updates_to_registry(
        registry_input,
        candidates,
        mode,
    )

    update_roots = [update["applied_update_root"] for update in accepted_updates]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    engine_root = _hash_json(
        {
            "applied_update_roots": sorted(update_roots),
            "refusal_roots": sorted(refusal_roots),
            "source_family_update_count": source_family_update_count,
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
    status = DRY_RUN_STATUS if mode == "dry-run" else APPLIED_STATUS
    applied_update_count = len(accepted_updates) if mode == "apply" else 0
    preview_update_count = len(accepted_updates)
    report = _build_report(
        status,
        mode,
        accepted_updates,
        refusals,
        source_family_update_count,
        engine_root,
    )
    summary = {
        "apply_registry_updates_status": status,
        "mode": mode,
        "registry_update_candidate_count": len(candidates),
        "preview_update_count": preview_update_count,
        "applied_update_count": applied_update_count,
        "source_family_update_count": source_family_update_count if mode == "apply" else 0,
        "refusal_count": len(refusals),
        "quotes_created": 0,
        "timestamps_created": 0,
        "transcripts_created": 0,
        "claims_created": 0,
        "contradictions_created": 0,
        "evidence_approved_count": 0,
        "applied_update_roots": update_roots,
        "refusal_roots": refusal_roots,
        "apply_registry_updates_report_hash": _sha256_text(report),
        "apply_registry_updates_root": engine_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "search_endpoints_applied": 0,
        "no_generated_outputs_committed": True,
    }
    if len(refusals) == 0 and preview_update_count != len(candidates):
        raise ValueError("All valid candidates must be previewed or applied")
    if summary["search_endpoints_applied"] != 0:
        raise ValueError("Search endpoints must not be applied")
    for counter_name in (
        "quotes_created",
        "timestamps_created",
        "transcripts_created",
        "claims_created",
        "contradictions_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0")
    if not _closed_flags(summary):
        raise ValueError("Apply registry updates guardrails must remain closed")

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(
        APPLIED_OUTPUT,
        {
            "applied_registry_updates": accepted_updates,
            "apply_registry_update_refusals": refusals,
        },
    )
    _write_json(PREVIEW_OUTPUT, updated_registry)
    _write_text(REPORT_OUTPUT, report)

    if mode == "apply":
        registry_input_path.write_text(
            json.dumps(updated_registry, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return {
        "summary": summary,
        "applied_registry_updates": accepted_updates,
        "apply_registry_update_refusals": refusals,
        "updated_source_registry_preview": updated_registry,
        "report": report,
    }
