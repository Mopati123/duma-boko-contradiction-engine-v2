#!/usr/bin/env python3
"""
Manual BEFORE Source Snapshot Intake.

Validates human-supplied BEFORE source snapshots for temporal sources that
cannot be live-harvested. This lane does not fetch URLs, search the web, modify
the source pack, localize content, create packets, extract claims, normalize
claims, create contradictions, pair claims, create proof chains, create final
reports, mark production readiness, or approve evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple
import hashlib
import json


DEFAULT_TEMPLATE = Path(
    "inputs/temporal_sources/manual_before_source_snapshot_template.json"
)
DEFAULT_SOURCE_PACK = Path("inputs/temporal_sources/duma_boko_temporal_source_pack.json")
DEFAULT_OUTPUT_DIR = Path("outputs/manual_before_source_snapshot_intake")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_before_source_snapshot_intake_summary.json"
VALIDATED_OUTPUT = DEFAULT_OUTPUT_DIR / "validated_manual_before_snapshots.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_before_source_snapshot_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_before_source_snapshot_intake_report.md"

SCHEMA_VERSION = "manual_before_source_snapshot_intake_v1"
TEMPLATE_VERSION = "manual_before_source_snapshot_template_v1"
SOURCE_PACK_VERSION = "duma_boko_temporal_source_pack_v2"

DRY_RUN_STATUS = "MANUAL_BEFORE_SOURCE_SNAPSHOT_INTAKE_DRY_RUN_VALIDATED"
VALIDATED_STATUS = "MANUAL_BEFORE_SOURCE_SNAPSHOT_INTAKE_VALIDATED"
PARTIAL_STATUS = "MANUAL_BEFORE_SOURCE_SNAPSHOT_INTAKE_PARTIAL"
REFUSED_STATUS = "MANUAL_BEFORE_SOURCE_SNAPSHOT_INTAKE_REFUSED"

VALIDATION_STATUS = "VALIDATED_MANUAL_BEFORE_SOURCE_SNAPSHOT"
TEMPORAL_POSITION = "BEFORE"
UNSPECIFIED = "UNSPECIFIED"

SNAPSHOT_FIELDS = (
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
VALIDATED_SNAPSHOT_FIELDS = (
    *SNAPSHOT_FIELDS,
    "time_direction",
    "validation_status",
    "linked_before_source_record_hash",
    "snapshot_text_hash",
    "metadata_hash",
    "snapshot_root",
)
REFUSAL_FIELDS = (
    "refusal_id",
    "snapshot_id",
    "linked_before_source_id",
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
    "REFUSED_EMPTY_SNAPSHOT",
    "REFUSED_UNKNOWN_BEFORE_SOURCE",
    "REFUSED_METADATA_MISMATCH",
    "REFUSED_MALFORMED_SNAPSHOT_RECORD",
    "REFUSED_DUPLICATE_SNAPSHOT_ID",
    "REFUSED_DUPLICATE_LINKED_BEFORE_SOURCE",
    "REFUSED_NON_BEFORE_SOURCE",
    "REFUSED_UNRESOLVED_BEFORE_SOURCE",
    "REFUSED_INPUT_VALIDATION",
)
METADATA_MATCH_FIELDS = (
    "url",
    "title",
    "publisher",
    "published_date",
    "topic",
    "source_type",
    "linked_claim_id",
)


class ManualBeforeSnapshotRefusal(ValueError):
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


def _closed_flags(data: Dict[str, Any]) -> bool:
    return (
        data.get("production_ready") is False
        and data.get("approved_evidence") == 0
        and data.get("public_ready") is False
        and data.get("institutional_ready") is False
    )


def _load_source_pack(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    if not isinstance(payload, dict) or not payload:
        raise ValueError("duma_boko_temporal_source_pack.json is missing.")
    if payload.get("pack_version") != SOURCE_PACK_VERSION:
        raise ValueError("source pack version is unsupported.")
    sources = payload.get("curated_temporal_sources")
    if not isinstance(sources, list):
        raise ValueError("source pack curated_temporal_sources must be a list.")
    for source in sources:
        if not isinstance(source, dict) or set(source.keys()) != set(SOURCE_PACK_FIELDS):
            raise ValueError("source pack record fields changed unexpectedly.")
    return sources


def _source_lookup(sources: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for source in sources:
        source_id = source["source_id"]
        if source_id in lookup:
            raise ValueError(f"duplicate source_id in source pack: {source_id}")
        lookup[source_id] = source
    return lookup


def _load_snapshot_template(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    if not isinstance(payload, dict) or not payload:
        raise ValueError("manual_before_source_snapshot_template.json is missing.")
    if payload.get("template_version") != TEMPLATE_VERSION:
        raise ValueError("manual BEFORE snapshot template version is unsupported.")
    if payload.get("manual_review_required") is not True:
        raise ValueError("manual BEFORE snapshot template manual_review_required must be true.")
    if payload.get("production_ready") is not False:
        raise ValueError("manual BEFORE snapshot template production_ready must be false.")
    snapshots = payload.get("manual_before_source_snapshots")
    if not isinstance(snapshots, list):
        raise ValueError("manual_before_source_snapshots must be a list.")
    return snapshots


def _source_notes(source: Dict[str, Any]) -> str:
    return str(source.get("notes") or "")


def _validate_snapshot_shape(snapshot: Dict[str, Any]) -> None:
    if not isinstance(snapshot, dict) or set(snapshot.keys()) != set(SNAPSHOT_FIELDS):
        raise ManualBeforeSnapshotRefusal(
            "REFUSED_MALFORMED_SNAPSHOT_RECORD",
            "Manual BEFORE snapshot fields do not match template schema.",
        )
    for field_name in SNAPSHOT_FIELDS:
        if field_name == "manual_review_required":
            continue
        value = snapshot.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ManualBeforeSnapshotRefusal(
                "REFUSED_MALFORMED_SNAPSHOT_RECORD",
                f"Manual BEFORE snapshot field {field_name} must be a non-empty string.",
            )
    if snapshot["manual_review_required"] is not True:
        raise ManualBeforeSnapshotRefusal(
            "REFUSED_MALFORMED_SNAPSHOT_RECORD",
            "Manual BEFORE snapshot manual_review_required must be true.",
        )


def _validate_linkage_and_metadata(
    snapshot: Dict[str, Any],
    source_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    source_id = snapshot["linked_before_source_id"]
    source = source_by_id.get(source_id)
    if source is None:
        raise ManualBeforeSnapshotRefusal(
            "REFUSED_UNKNOWN_BEFORE_SOURCE",
            f"Unknown BEFORE source id: {source_id}.",
        )
    if source["time_direction"] != TEMPORAL_POSITION:
        raise ManualBeforeSnapshotRefusal(
            "REFUSED_NON_BEFORE_SOURCE",
            f"Linked source {source_id} is not a BEFORE source.",
        )
    for field_name in METADATA_MATCH_FIELDS:
        source_value = str(source.get(field_name) or "")
        if snapshot[field_name] != source_value:
            raise ManualBeforeSnapshotRefusal(
                "REFUSED_METADATA_MISMATCH",
                f"Snapshot {field_name} does not match linked BEFORE source.",
            )
    if snapshot["verification_notes"] != _source_notes(source):
        raise ManualBeforeSnapshotRefusal(
            "REFUSED_METADATA_MISMATCH",
            "Snapshot verification_notes does not match linked BEFORE source notes.",
        )
    return source


def _validate_snapshot_records(
    snapshots: List[Dict[str, Any]],
    source_by_id: Dict[str, Dict[str, Any]],
) -> None:
    seen_snapshot_ids = set()
    seen_source_ids = set()
    for snapshot in snapshots:
        _validate_snapshot_shape(snapshot)
        snapshot_id = snapshot["snapshot_id"]
        source_id = snapshot["linked_before_source_id"]
        if snapshot_id in seen_snapshot_ids:
            raise ManualBeforeSnapshotRefusal(
                "REFUSED_DUPLICATE_SNAPSHOT_ID",
                f"Duplicate snapshot_id: {snapshot_id}.",
            )
        if source_id in seen_source_ids:
            raise ManualBeforeSnapshotRefusal(
                "REFUSED_DUPLICATE_LINKED_BEFORE_SOURCE",
                f"Duplicate linked_before_source_id: {source_id}.",
            )
        seen_snapshot_ids.add(snapshot_id)
        seen_source_ids.add(source_id)
        _validate_linkage_and_metadata(snapshot, source_by_id)


def _source_record_hash(source: Dict[str, Any]) -> str:
    return _hash_json({field_name: source[field_name] for field_name in SOURCE_PACK_FIELDS})


def _metadata_hash(snapshot: Dict[str, Any], source: Dict[str, Any]) -> str:
    return _hash_json(
        {
            "snapshot_id": snapshot["snapshot_id"],
            "linked_before_source_id": snapshot["linked_before_source_id"],
            "url": snapshot["url"],
            "title": snapshot["title"],
            "publisher": snapshot["publisher"],
            "published_date": snapshot["published_date"],
            "topic": snapshot["topic"],
            "source_type": snapshot["source_type"],
            "linked_claim_id": snapshot["linked_claim_id"],
            "verification_notes": snapshot["verification_notes"],
            "source_record_hash": _source_record_hash(source),
        }
    )


def _snapshot_root_material(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(snapshot)
    material.pop("snapshot_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _validated_snapshot(snapshot: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    validated = {
        **snapshot,
        "time_direction": TEMPORAL_POSITION,
        "validation_status": VALIDATION_STATUS,
        "linked_before_source_record_hash": _source_record_hash(source),
        "snapshot_text_hash": _sha256_text(snapshot["snapshot_text"]),
        "metadata_hash": _metadata_hash(snapshot, source),
        "snapshot_root": "",
    }
    validated["snapshot_root"] = _hash_json(_snapshot_root_material(validated))
    return validated


def _snapshot_identity(snapshot: Any) -> Tuple[str, str, str]:
    if not isinstance(snapshot, dict):
        return ("UNKNOWN_SNAPSHOT", "UNKNOWN_BEFORE_SOURCE", "")
    return (
        str(snapshot.get("snapshot_id") or "UNKNOWN_SNAPSHOT"),
        str(snapshot.get("linked_before_source_id") or "UNKNOWN_BEFORE_SOURCE"),
        str(snapshot.get("url") or ""),
    )


def _make_refusal(snapshot: Any, code: str, reason: str) -> Dict[str, Any]:
    snapshot_id, source_id, url = _snapshot_identity(snapshot)
    refusal = {
        "refusal_id": f"MANUAL_BEFORE_SOURCE_SNAPSHOT_REFUSAL_{snapshot_id}",
        "snapshot_id": snapshot_id,
        "linked_before_source_id": source_id,
        "url": url,
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


def _validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Manual BEFORE snapshot refusal fields changed unexpectedly.")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError("Manual BEFORE snapshot refusal_code unsupported.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("Manual BEFORE snapshot refusal manual_review_required must be true.")
    if not _closed_flags(refusal):
        raise ValueError("Manual BEFORE snapshot refusal guardrails must remain closed.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}.")


def _validate_validated_snapshot(snapshot: Dict[str, Any]) -> None:
    if set(snapshot.keys()) != set(VALIDATED_SNAPSHOT_FIELDS):
        raise ValueError("Validated manual BEFORE snapshot fields changed unexpectedly.")
    if snapshot["validation_status"] != VALIDATION_STATUS:
        raise ValueError("Validated manual BEFORE snapshot validation_status unsupported.")
    if snapshot["time_direction"] != TEMPORAL_POSITION:
        raise ValueError("Validated manual BEFORE snapshot time_direction must be BEFORE.")
    if snapshot["manual_review_required"] is not True:
        raise ValueError("Validated manual BEFORE snapshot manual_review_required must be true.")
    if not snapshot["snapshot_text"].strip() or snapshot["snapshot_text"].strip() == UNSPECIFIED:
        raise ValueError("Validated manual BEFORE snapshot cannot contain placeholder text.")
    if snapshot["snapshot_text_hash"] != _sha256_text(snapshot["snapshot_text"]):
        raise ValueError(f"snapshot_text_hash mismatch for {snapshot['snapshot_id']}.")
    if snapshot["snapshot_root"] != _hash_json(_snapshot_root_material(snapshot)):
        raise ValueError(f"snapshot_root mismatch for {snapshot['snapshot_id']}.")


def _build_validated_snapshots(
    snapshots: List[Dict[str, Any]],
    source_by_id: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    validated_snapshots: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    seen_snapshot_ids = set()
    seen_source_ids = set()

    for snapshot in snapshots:
        try:
            _validate_snapshot_shape(snapshot)
            snapshot_id = snapshot["snapshot_id"]
            source_id = snapshot["linked_before_source_id"]
            if snapshot_id in seen_snapshot_ids:
                raise ManualBeforeSnapshotRefusal(
                    "REFUSED_DUPLICATE_SNAPSHOT_ID",
                    f"Duplicate snapshot_id: {snapshot_id}.",
                )
            if source_id in seen_source_ids:
                raise ManualBeforeSnapshotRefusal(
                    "REFUSED_DUPLICATE_LINKED_BEFORE_SOURCE",
                    f"Duplicate linked_before_source_id: {source_id}.",
                )
            seen_snapshot_ids.add(snapshot_id)
            seen_source_ids.add(source_id)
            source = _validate_linkage_and_metadata(snapshot, source_by_id)
            if not snapshot["snapshot_text"].strip() or snapshot["snapshot_text"].strip() == UNSPECIFIED:
                raise ManualBeforeSnapshotRefusal(
                    "REFUSED_EMPTY_SNAPSHOT",
                    "Manual BEFORE snapshot_text is empty or UNSPECIFIED.",
                )
            if snapshot["url"] == UNSPECIFIED or source["url"] == UNSPECIFIED:
                raise ManualBeforeSnapshotRefusal(
                    "REFUSED_UNRESOLVED_BEFORE_SOURCE",
                    "Manual BEFORE snapshot is linked to an unresolved source URL.",
                )
            validated = _validated_snapshot(snapshot, source)
            _validate_validated_snapshot(validated)
            validated_snapshots.append(validated)
        except ManualBeforeSnapshotRefusal as exc:
            refusal = _make_refusal(snapshot, exc.code, exc.reason)
            _validate_refusal(refusal)
            refusals.append(refusal)
        except ValueError as exc:
            refusal = _make_refusal(snapshot, "REFUSED_INPUT_VALIDATION", str(exc))
            _validate_refusal(refusal)
            refusals.append(refusal)

    return validated_snapshots, refusals


def _status_for(mode: str, validated_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if validated_count > 0 and refusal_count == 0:
        return VALIDATED_STATUS
    if validated_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _schema_payload() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "template_version": TEMPLATE_VERSION,
        "source_pack_version": SOURCE_PACK_VERSION,
        "snapshot_fields": list(SNAPSHOT_FIELDS),
        "validated_snapshot_fields": list(VALIDATED_SNAPSHOT_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
    }


def _summary_root_material(summary: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {
        "manual_before_source_snapshot_intake_root",
        "manual_before_source_snapshot_intake_report_hash",
    }
    return {key: value for key, value in summary.items() if key not in excluded}


def _build_report(
    status: str,
    mode: str,
    snapshot_count: int,
    validated_snapshots: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    validated_lines = ["- None"]
    if validated_snapshots:
        validated_lines = [
            f"- {snapshot['snapshot_id']}: {snapshot['linked_before_source_id']}"
            for snapshot in validated_snapshots[:20]
        ]
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = [
            f"- {refusal['snapshot_id']}: {refusal['refusal_code']}"
            for refusal in refusals[:20]
        ]
    return "\n".join(
        [
            "# Manual BEFORE Source Snapshot Intake Report",
            "",
            f"- manual_before_source_snapshot_intake_status: {status}",
            f"- mode: {mode}",
            f"- snapshot_template_count: {snapshot_count}",
            f"- validated_snapshot_count: {len(validated_snapshots)}",
            f"- refusal_count: {len(refusals)}",
            f"- manual_before_source_snapshot_intake_root: {root}",
            "",
            "## Validated Snapshots",
            *validated_lines,
            "",
            "## Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- URLs Fetched: 0",
            "- Web Searches Performed: 0",
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


def build_manual_before_source_snapshot_intake(
    mode: str = "dry-run",
    snapshot_template_path: Path = DEFAULT_TEMPLATE,
    source_pack_path: Path = DEFAULT_SOURCE_PACK,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "validate"):
        raise ValueError("mode must be 'dry-run' or 'validate'.")

    sources = _load_source_pack(source_pack_path)
    source_by_id = _source_lookup(sources)
    snapshots = _load_snapshot_template(snapshot_template_path)
    if mode == "dry-run":
        _validate_snapshot_records(snapshots, source_by_id)

    validated_snapshots: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    if mode == "validate":
        validated_snapshots, refusals = _build_validated_snapshots(snapshots, source_by_id)

    schema = _schema_payload()
    status = _status_for(mode, len(validated_snapshots), len(refusals))
    summary = {
        "manual_before_source_snapshot_intake_status": status,
        "mode": mode,
        "snapshot_template_count": len(snapshots),
        "validated_snapshot_count": len(validated_snapshots),
        "refusal_count": len(refusals),
        "validated_snapshot_ids": [snapshot["snapshot_id"] for snapshot in validated_snapshots],
        "validated_snapshot_roots": [snapshot["snapshot_root"] for snapshot in validated_snapshots],
        "refusal_roots": [refusal["refusal_root"] for refusal in refusals],
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "manual_before_source_snapshot_intake_schema_hash": _hash_json(schema),
        "manual_before_source_snapshot_intake_report_hash": "",
        "manual_before_source_snapshot_intake_root": "",
        "urls_invented": 0,
        "web_searches_performed": 0,
        "urls_fetched": 0,
        "live_web_access_performed": 0,
        "llm_calls": 0,
        "embeddings_created": 0,
        "localized_segments_created": 0,
        "packets_created": 0,
        "claims_created": 0,
        "claims_rewritten": 0,
        "claims_normalized_semantically": 0,
        "contradictions_created": 0,
        "claim_pairs_created": 0,
        "source_pack_modified": False,
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
    summary["manual_before_source_snapshot_intake_root"] = _hash_json(
        _summary_root_material(summary)
    )
    report = _build_report(
        status,
        mode,
        len(snapshots),
        validated_snapshots,
        refusals,
        summary["manual_before_source_snapshot_intake_root"],
    )
    summary["manual_before_source_snapshot_intake_report_hash"] = _sha256_text(report)
    summary["manual_before_source_snapshot_intake_root"] = _hash_json(
        _summary_root_material(summary)
    )
    report = _build_report(
        status,
        mode,
        len(snapshots),
        validated_snapshots,
        refusals,
        summary["manual_before_source_snapshot_intake_root"],
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
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0.")
    if summary["source_pack_modified"] is not False:
        raise ValueError("source_pack_modified must remain false.")
    if not _closed_flags(summary):
        raise ValueError("Manual BEFORE snapshot intake guardrails must remain closed.")

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(
        output_dir / VALIDATED_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "validated_manual_before_snapshots": validated_snapshots,
        },
    )
    _write_json(
        output_dir / REFUSALS_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "manual_before_source_snapshot_refusals": refusals,
        },
    )
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    return {
        "summary": summary,
        "validated_manual_before_snapshots": validated_snapshots,
        "manual_before_source_snapshot_refusals": refusals,
        "schema": schema,
        "report": report,
    }


__all__ = ["build_manual_before_source_snapshot_intake"]
