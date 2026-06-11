#!/usr/bin/env python3
"""
Manual BEFORE Snapshot to Harvested Source.

Converts validated manual BEFORE source snapshots into temporal source
harvester-compatible records without fetching URLs or inventing content. This
lane does not localize content, generate evidence packets, extract claims,
normalize claims, pair claims, create contradictions, create embeddings, create
proof chains, create final reports, mark production readiness, or approve
evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json


DEFAULT_VALIDATED_SNAPSHOTS = Path(
    "outputs/manual_before_source_snapshot_intake/validated_manual_before_snapshots.json"
)
DEFAULT_SNAPSHOT_SUMMARY = Path(
    "outputs/manual_before_source_snapshot_intake/"
    "manual_before_source_snapshot_intake_summary.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/temporal_source_harvester")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_source_harvester_summary.json"
HARVESTED_OUTPUT = DEFAULT_OUTPUT_DIR / "harvested_temporal_sources.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_source_harvester_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_source_harvester_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_source_harvester_schema.json"

SCHEMA_VERSION = "temporal_source_harvester_v2"
LANE_SCHEMA_VERSION = "manual_before_snapshot_to_harvested_source_v1"
UPSTREAM_SCHEMA_VERSION = "manual_before_source_snapshot_intake_v1"
UPSTREAM_VALIDATED_STATUS = "MANUAL_BEFORE_SOURCE_SNAPSHOT_INTAKE_VALIDATED"
UPSTREAM_PARTIAL_STATUS = "MANUAL_BEFORE_SOURCE_SNAPSHOT_INTAKE_PARTIAL"
SNAPSHOT_VALIDATION_STATUS = "VALIDATED_MANUAL_BEFORE_SOURCE_SNAPSHOT"

DRY_RUN_STATUS = "TEMPORAL_SOURCE_HARVESTER_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "TEMPORAL_SOURCE_HARVESTER_CANDIDATE"
PARTIAL_STATUS = "TEMPORAL_SOURCE_HARVESTER_PARTIAL"
REFUSED_STATUS = "TEMPORAL_SOURCE_HARVESTER_REFUSED"

TEMPORAL_POSITION = "BEFORE"
CONTENT_TYPE = "MANUAL_BEFORE_SOURCE_SNAPSHOT"
HARVEST_METHOD = "MANUAL_BEFORE_SOURCE_SNAPSHOT_NO_FETCH"
UNSPECIFIED = "UNSPECIFIED"

VALIDATED_SNAPSHOT_FIELDS = (
    "snapshot_id",
    "linked_before_source_id",
    "url",
    "title",
    "publisher",
    "published_date",
    "topic",
    "source_type",
    "linked_claim_id",
    "verification_notes",
    "snapshot_text",
    "manual_review_required",
    "time_direction",
    "validation_status",
    "linked_before_source_record_hash",
    "snapshot_text_hash",
    "metadata_hash",
    "snapshot_root",
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
    "REFUSED_MISSING_VALIDATED_SNAPSHOTS",
    "REFUSED_UPSTREAM_STATUS",
    "REFUSED_NO_VALIDATED_MANUAL_BEFORE_SNAPSHOTS",
    "REFUSED_MALFORMED_VALIDATED_SNAPSHOT",
    "REFUSED_NON_BEFORE_SNAPSHOT",
    "REFUSED_UNVALIDATED_SNAPSHOT",
    "REFUSED_EMPTY_SNAPSHOT_TEXT",
    "REFUSED_SNAPSHOT_TEXT_HASH_MISMATCH",
    "REFUSED_DUPLICATE_BEFORE_SOURCE",
    "REFUSED_HARVESTED_HASH_MISMATCH",
)


class ManualBeforeHarvestRefusal(ValueError):
    def __init__(self, code: str, reason: str):
        super().__init__(reason)
        self.code = code
        self.reason = reason


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def _closed_flags(data: Dict[str, Any]) -> bool:
    return (
        data.get("production_ready") is False
        and data.get("approved_evidence") == 0
        and data.get("public_ready") is False
        and data.get("institutional_ready") is False
    )


def _load_validated_snapshots(path: Path) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    payload = _load_json(path)
    if not isinstance(payload, dict) or not payload:
        return [], "validated_manual_before_snapshots.json is missing."
    if payload.get("schema_version") != UPSTREAM_SCHEMA_VERSION:
        return [], "validated_manual_before_snapshots schema_version is unsupported."
    snapshots = payload.get("validated_manual_before_snapshots")
    if not isinstance(snapshots, list):
        return [], "validated_manual_before_snapshots must contain a list."
    return snapshots, None


def _load_upstream_summary(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    summary = _load_json(path)
    if not isinstance(summary, dict) or not summary:
        return None, "manual_before_source_snapshot_intake_summary.json is missing."
    return summary, None


def _validate_upstream_summary(summary: Dict[str, Any], snapshot_count: int) -> None:
    status = summary.get("manual_before_source_snapshot_intake_status")
    if status not in (UPSTREAM_VALIDATED_STATUS, UPSTREAM_PARTIAL_STATUS):
        raise ManualBeforeHarvestRefusal(
            "REFUSED_UPSTREAM_STATUS",
            f"Manual BEFORE snapshot intake status is {status}, not validated or partial.",
        )
    if summary.get("validated_snapshot_count") != snapshot_count:
        raise ManualBeforeHarvestRefusal(
            "REFUSED_UPSTREAM_STATUS",
            "Manual BEFORE snapshot intake count does not match validated snapshot payload.",
        )
    for counter_name in (
        "urls_invented",
        "web_searches_performed",
        "urls_fetched",
        "live_web_access_performed",
        "llm_calls",
        "embeddings_created",
        "localized_segments_created",
        "packets_created",
        "claims_created",
        "claims_rewritten",
        "claims_normalized_semantically",
        "contradictions_created",
        "claim_pairs_created",
        "proof_chains_created",
        "final_reports_created",
    ):
        if summary.get(counter_name) != 0:
            raise ManualBeforeHarvestRefusal(
                "REFUSED_UPSTREAM_STATUS",
                f"Upstream guardrail {counter_name} must remain 0.",
            )
    if summary.get("source_pack_modified") is not False:
        raise ManualBeforeHarvestRefusal(
            "REFUSED_UPSTREAM_STATUS",
            "Upstream source_pack_modified must remain false.",
        )
    if not _closed_flags(summary):
        raise ManualBeforeHarvestRefusal(
            "REFUSED_UPSTREAM_STATUS",
            "Upstream manual BEFORE snapshot intake governance flags must remain closed.",
        )


def _require_nonempty_string(data: Dict[str, Any], field_name: str, code: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ManualBeforeHarvestRefusal(code, f"{field_name} must be a non-empty string.")


def _validate_snapshot(snapshot: Dict[str, Any]) -> None:
    if not isinstance(snapshot, dict) or set(snapshot.keys()) != set(VALIDATED_SNAPSHOT_FIELDS):
        raise ManualBeforeHarvestRefusal(
            "REFUSED_MALFORMED_VALIDATED_SNAPSHOT",
            "Validated manual BEFORE snapshot fields do not match upstream schema.",
        )
    for field_name in VALIDATED_SNAPSHOT_FIELDS:
        if field_name == "manual_review_required":
            continue
        _require_nonempty_string(
            snapshot,
            field_name,
            "REFUSED_MALFORMED_VALIDATED_SNAPSHOT",
        )
    if snapshot["time_direction"] != TEMPORAL_POSITION:
        raise ManualBeforeHarvestRefusal(
            "REFUSED_NON_BEFORE_SNAPSHOT",
            "Validated manual snapshot time_direction must be BEFORE.",
        )
    if snapshot["validation_status"] != SNAPSHOT_VALIDATION_STATUS:
        raise ManualBeforeHarvestRefusal(
            "REFUSED_UNVALIDATED_SNAPSHOT",
            "Snapshot validation_status is not VALIDATED_MANUAL_BEFORE_SOURCE_SNAPSHOT.",
        )
    if snapshot["manual_review_required"] is not True:
        raise ManualBeforeHarvestRefusal(
            "REFUSED_MALFORMED_VALIDATED_SNAPSHOT",
            "Validated manual snapshot manual_review_required must be true.",
        )
    if snapshot["snapshot_text"].strip() == UNSPECIFIED:
        raise ManualBeforeHarvestRefusal(
            "REFUSED_EMPTY_SNAPSHOT_TEXT",
            "Validated manual snapshot text cannot be UNSPECIFIED.",
        )
    if snapshot["snapshot_text_hash"] != _sha256_text(snapshot["snapshot_text"]):
        raise ManualBeforeHarvestRefusal(
            "REFUSED_SNAPSHOT_TEXT_HASH_MISMATCH",
            f"snapshot_text_hash mismatch for {snapshot['snapshot_id']}.",
        )


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


def _make_harvested_source(snapshot: Dict[str, Any], index: int) -> Dict[str, Any]:
    content_bytes = snapshot["snapshot_text"].encode("utf-8")
    source = {
        "harvested_temporal_source_id": (
            f"HARVESTED_TEMPORAL_SOURCE_MANUAL_BEFORE_{index:06d}"
        ),
        "source_id": snapshot["linked_before_source_id"],
        "time_direction": TEMPORAL_POSITION,
        "source_type": snapshot["source_type"],
        "url": snapshot["url"],
        "title": snapshot["title"],
        "publisher": snapshot["publisher"],
        "published_date": snapshot["published_date"],
        "topic": snapshot["topic"],
        "http_status": 0,
        "content_type": CONTENT_TYPE,
        "content_length": len(content_bytes),
        "content_sha256": _sha256_bytes(content_bytes),
        "text_excerpt": snapshot["snapshot_text"],
        "harvest_method": HARVEST_METHOD,
        "manual_review_required": True,
        "metadata_hash": "",
        "harvest_root": "",
    }
    source["metadata_hash"] = _hash_json(_harvested_metadata_material(source))
    source["harvest_root"] = _hash_json(_harvest_root_material(source))
    return source


def _validate_harvested_source(source: Dict[str, Any], snapshot: Dict[str, Any]) -> None:
    if set(source.keys()) != set(HARVESTED_FIELDS):
        raise ValueError("Harvested temporal source fields changed unexpectedly.")
    for field_name in HARVESTED_FIELDS:
        if field_name in ("http_status", "content_length", "manual_review_required"):
            continue
        _require_nonempty_string(source, field_name, "REFUSED_HARVESTED_HASH_MISMATCH")
    if source["source_id"] != snapshot["linked_before_source_id"]:
        raise ValueError("Harvested source_id does not preserve linked_before_source_id.")
    if source["time_direction"] != TEMPORAL_POSITION:
        raise ValueError("Harvested source time_direction must be BEFORE.")
    if source["text_excerpt"] != snapshot["snapshot_text"]:
        raise ValueError("Harvested text_excerpt must exactly equal snapshot_text.")
    if source["content_sha256"] != _sha256_bytes(snapshot["snapshot_text"].encode("utf-8")):
        raise ValueError("Harvested content_sha256 must hash exact snapshot_text bytes.")
    if source["http_status"] != 0:
        raise ValueError("Manual BEFORE harvested source http_status must remain 0.")
    if source["content_type"] != CONTENT_TYPE or source["harvest_method"] != HARVEST_METHOD:
        raise ValueError("Manual BEFORE harvested source no-fetch audit fields changed.")
    if source["manual_review_required"] is not True:
        raise ValueError("Harvested source manual_review_required must remain true.")
    if source["metadata_hash"] != _hash_json(_harvested_metadata_material(source)):
        raise ValueError(f"metadata_hash mismatch for {source['source_id']}.")
    if source["harvest_root"] != _hash_json(_harvest_root_material(source)):
        raise ValueError(f"harvest_root mismatch for {source['source_id']}.")


def _snapshot_identity(snapshot: Any) -> Tuple[str, str]:
    if not isinstance(snapshot, dict):
        return ("UNKNOWN_MANUAL_BEFORE_SOURCE", "")
    return (
        str(snapshot.get("linked_before_source_id") or "UNKNOWN_MANUAL_BEFORE_SOURCE"),
        str(snapshot.get("url") or ""),
    )


def _make_refusal(snapshot: Any, code: str, reason: str) -> Dict[str, Any]:
    source_id, url = _snapshot_identity(snapshot)
    refusal = {
        "refusal_id": f"TEMPORAL_SOURCE_HARVESTER_REFUSAL_{source_id}",
        "source_id": source_id,
        "url": url,
        "refusal_code": code,
        "refusal_reason": reason,
        "manual_review_required": True,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def _validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Temporal source harvester refusal fields changed unexpectedly.")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError("Temporal source harvester refusal_code unsupported.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("Temporal source harvester refusal manual_review_required must remain true.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}.")


def _harvest_or_refuse(
    snapshot: Dict[str, Any],
    index: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    try:
        _validate_snapshot(snapshot)
        harvested = _make_harvested_source(snapshot, index)
        _validate_harvested_source(harvested, snapshot)
        return harvested, None
    except ManualBeforeHarvestRefusal as exc:
        refusal = _make_refusal(snapshot, exc.code, exc.reason)
        _validate_refusal(refusal)
        return None, refusal
    except ValueError as exc:
        refusal = _make_refusal(snapshot, "REFUSED_HARVESTED_HASH_MISMATCH", str(exc))
        _validate_refusal(refusal)
        return None, refusal


def _status_for(mode: str, harvested_count: int, refusal_count: int) -> str:
    if mode == "dry-run" and refusal_count == 0:
        return DRY_RUN_STATUS
    if harvested_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if harvested_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _schema_payload() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "lane_schema_version": LANE_SCHEMA_VERSION,
        "upstream_schema_version": UPSTREAM_SCHEMA_VERSION,
        "validated_snapshot_fields": list(VALIDATED_SNAPSHOT_FIELDS),
        "harvested_source_fields": list(HARVESTED_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "no_fetch_harvest_method": HARVEST_METHOD,
        "manual_before_snapshot_to_harvested_source_only": True,
    }


def _summary_root_material(summary: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {
        "temporal_source_harvester_root",
        "temporal_source_harvester_report_hash",
    }
    return {key: value for key, value in summary.items() if key not in excluded}


def _build_report(
    status: str,
    mode: str,
    snapshot_count: int,
    harvested_sources: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    harvested_lines = ["- None"]
    if harvested_sources:
        harvested_lines = [
            f"- {source['harvested_temporal_source_id']}: {source['source_id']}"
            for source in harvested_sources[:20]
        ]
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = [
            f"- {refusal['source_id']}: {refusal['refusal_code']}"
            for refusal in refusals[:20]
        ]
    return "\n".join(
        [
            "# Manual BEFORE Snapshot To Harvested Source Report",
            "",
            f"- temporal_source_harvester_status: {status}",
            f"- mode: {mode}",
            f"- validated_manual_before_snapshot_count: {snapshot_count}",
            f"- harvested_temporal_source_count: {len(harvested_sources)}",
            f"- refusal_count: {len(refusals)}",
            f"- temporal_source_harvester_root: {root}",
            "",
            "## Harvested Sources",
            *harvested_lines,
            "",
            "## Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- URLs Fetched: 0",
            "- Live Web Access Performed: 0",
            "- LLM Calls: 0",
            "- Embeddings Created: 0",
            "- Localized Segments Created: 0",
            "- Packets Created: 0",
            "- Claims Created: 0",
            "- Contradictions Created: 0",
            "- Claim Pairs Created: 0",
            "- Proof Chains Created: 0",
            "- Final Reports Created: 0",
            "- Approved Evidence: 0",
            "- Production Ready: False",
            "",
        ]
    )


def build_manual_before_snapshot_to_harvested_source(
    mode: str = "dry-run",
    validated_snapshots_path: Path = DEFAULT_VALIDATED_SNAPSHOTS,
    snapshot_summary_path: Path = DEFAULT_SNAPSHOT_SUMMARY,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "from-snapshots"):
        raise ValueError("mode must be 'dry-run' or 'from-snapshots'.")

    snapshots, snapshot_error = _load_validated_snapshots(validated_snapshots_path)
    upstream_summary, summary_error = _load_upstream_summary(snapshot_summary_path)
    schema = _schema_payload()
    harvested_sources: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    validated_snapshot_count = 0

    if snapshot_error:
        refusals.append(
            _make_refusal({}, "REFUSED_MISSING_VALIDATED_SNAPSHOTS", snapshot_error)
        )
    elif summary_error:
        refusals.append(_make_refusal({}, "REFUSED_UPSTREAM_STATUS", summary_error))
    elif upstream_summary is not None:
        try:
            _validate_upstream_summary(upstream_summary, len(snapshots))
        except ManualBeforeHarvestRefusal as exc:
            refusals.append(_make_refusal({}, exc.code, exc.reason))

    if not refusals and not snapshots:
        refusals.append(
            _make_refusal(
                {},
                "REFUSED_NO_VALIDATED_MANUAL_BEFORE_SNAPSHOTS",
                "No validated manual BEFORE snapshots are available to harvest.",
            )
        )

    seen_source_ids = set()
    if not refusals:
        for snapshot in snapshots:
            source_id = str(snapshot.get("linked_before_source_id") or "")
            if source_id in seen_source_ids:
                refusal = _make_refusal(
                    snapshot,
                    "REFUSED_DUPLICATE_BEFORE_SOURCE",
                    f"Duplicate linked_before_source_id: {source_id}.",
                )
                _validate_refusal(refusal)
                refusals.append(refusal)
                continue
            seen_source_ids.add(source_id)
            if mode == "dry-run":
                try:
                    _validate_snapshot(snapshot)
                    validated_snapshot_count += 1
                except ManualBeforeHarvestRefusal as exc:
                    refusal = _make_refusal(snapshot, exc.code, exc.reason)
                    _validate_refusal(refusal)
                    refusals.append(refusal)
            else:
                harvested, refusal = _harvest_or_refuse(
                    snapshot,
                    len(harvested_sources) + 1,
                )
                if harvested is not None:
                    harvested_sources.append(harvested)
                    validated_snapshot_count += 1
                if refusal is not None:
                    refusals.append(refusal)

    for refusal in refusals:
        _validate_refusal(refusal)

    status = _status_for(mode, len(harvested_sources), len(refusals))
    summary = {
        "temporal_source_harvester_status": status,
        "mode": mode,
        "resolved_url_count": len(snapshots),
        "validated_manual_before_snapshot_count": len(snapshots),
        "validated_snapshot_count": validated_snapshot_count,
        "harvested_temporal_source_count": len(harvested_sources),
        "refusal_count": len(refusals),
        "before_source_count": sum(
            1 for source in harvested_sources if source["time_direction"] == TEMPORAL_POSITION
        ),
        "after_source_count": 0,
        "source_type_counts": {
            source_type: sum(
                1 for source in harvested_sources if source["source_type"] == source_type
            )
            for source_type in sorted({source["source_type"] for source in harvested_sources})
        },
        "unresolved_urls_harvested": 0,
        "manual_before_snapshot_no_fetch_harvest": True,
        "source_text_exact_copy": len(refusals) == 0,
        "source_lineage_preserved": len(refusals) == 0,
        "snapshot_text_hashes": [
            snapshot["snapshot_text_hash"]
            for snapshot in snapshots
            if isinstance(snapshot, dict) and "snapshot_text_hash" in snapshot
        ],
        "metadata_hashes": [source["metadata_hash"] for source in harvested_sources],
        "harvest_roots": [source["harvest_root"] for source in harvested_sources],
        "refusal_roots": [refusal["refusal_root"] for refusal in refusals],
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "temporal_source_harvester_schema_hash": _hash_json(schema),
        "temporal_source_harvester_report_hash": "",
        "temporal_source_harvester_root": "",
        "content_invented": 0,
        "urls_fetched": 0,
        "live_web_access_performed": 0,
        "llm_calls": 0,
        "embeddings_created": 0,
        "localized_segments_created": 0,
        "packets_created": 0,
        "quotes_created": 0,
        "quotes_invented": 0,
        "timestamps_created": 0,
        "claims_created": 0,
        "claims_rewritten": 0,
        "claims_normalized_semantically": 0,
        "contradictions_created": 0,
        "claim_pairs_created": 0,
        "proof_chains_created": 0,
        "final_reports_created": 0,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    summary["temporal_source_harvester_root"] = _hash_json(
        _summary_root_material(summary)
    )
    report = _build_report(
        status,
        mode,
        len(snapshots),
        harvested_sources,
        refusals,
        summary["temporal_source_harvester_root"],
    )
    summary["temporal_source_harvester_report_hash"] = _sha256_text(report)
    summary["temporal_source_harvester_root"] = _hash_json(
        _summary_root_material(summary)
    )
    report = _build_report(
        status,
        mode,
        len(snapshots),
        harvested_sources,
        refusals,
        summary["temporal_source_harvester_root"],
    )

    for counter_name in (
        "content_invented",
        "urls_fetched",
        "live_web_access_performed",
        "llm_calls",
        "embeddings_created",
        "localized_segments_created",
        "packets_created",
        "quotes_created",
        "quotes_invented",
        "timestamps_created",
        "claims_created",
        "claims_rewritten",
        "claims_normalized_semantically",
        "contradictions_created",
        "claim_pairs_created",
        "proof_chains_created",
        "final_reports_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0.")
    if not _closed_flags(summary):
        raise ValueError("Manual BEFORE harvested-source guardrails must remain closed.")

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(
        output_dir / HARVESTED_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "harvested_temporal_sources": harvested_sources,
        },
    )
    _write_json(
        output_dir / REFUSALS_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "temporal_source_harvester_refusals": refusals,
        },
    )
    _write_json(output_dir / SCHEMA_OUTPUT.name, schema)
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    return {
        "summary": summary,
        "harvested_temporal_sources": harvested_sources,
        "temporal_source_harvester_refusals": refusals,
        "schema": schema,
        "report": report,
    }


__all__ = ["build_manual_before_snapshot_to_harvested_source"]
