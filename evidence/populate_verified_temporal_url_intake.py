#!/usr/bin/env python3
"""
Populate Verified Temporal URL Intake v2.

Copies reviewed deep-research metadata into the verified temporal URL intake
template while preserving canonical intake slot identity. This lane does not
validate URLs, invent URLs or metadata, relax validators, update the curated
source pack, create quotes, timestamps, claims, contradictions, production
readiness, or approved evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple
import copy
import hashlib
import json


DEFAULT_METADATA_PACK = Path(
    "outputs/deep_research_temporal_metadata_pack/temporal_metadata_pack.json"
)
DEFAULT_INTAKE_TEMPLATE = Path(
    "inputs/temporal_sources/verified_temporal_url_intake_template.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/populate_verified_temporal_url_intake")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "populate_temporal_url_intake_summary.json"
PREVIEW_OUTPUT = DEFAULT_OUTPUT_DIR / "populated_temporal_url_intake_preview.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "populate_temporal_url_intake_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "populate_temporal_url_intake_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "populate_temporal_url_intake_schema.json"

SCHEMA_VERSION = "populate_verified_temporal_url_intake_v2"
UPSTREAM_SCHEMA_VERSION = "deep_research_temporal_metadata_pack_v2"
INTAKE_VERSION = "verified_temporal_url_intake_v2"

DRY_RUN_STATUS = "POPULATE_TEMPORAL_URL_INTAKE_DRY_RUN_PREVIEW"
APPLIED_STATUS = "POPULATE_TEMPORAL_URL_INTAKE_APPLIED"
PARTIAL_STATUS = "POPULATE_TEMPORAL_URL_INTAKE_PARTIAL"
REFUSED_STATUS = "POPULATE_TEMPORAL_URL_INTAKE_REFUSED"

UNSPECIFIED_URL = "UNSPECIFIED"
ALLOWED_UNSPECIFIED_SOURCE_ID = "CURATED_TEMPORAL_SOURCE_BEFORE_005_SOCIAL_MEDIA_POST"

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

METADATA_RECORD_FIELDS = (
    "source_id",
    "title",
    "publisher",
    "published_date",
    "source_type",
    "time_direction",
    "topic",
    "verification_notes",
    "url",
    "manual_review_required",
    "metadata_hash",
    "metadata_record_root",
)
INTAKE_FIELDS = (
    "source_id",
    "time_direction",
    "source_type",
    "url",
    "title",
    "publisher",
    "published_date",
    "topic",
    "linked_claim_id",
    "verification_notes",
)
COPIED_FIELDS = (
    "url",
    "title",
    "publisher",
    "published_date",
    "verification_notes",
)
PRESERVED_FIELDS = (
    "source_id",
    "time_direction",
    "source_type",
    "topic",
    "linked_claim_id",
)
REFUSAL_FIELDS = (
    "populate_temporal_url_intake_refusal_id",
    "source_id",
    "time_direction",
    "source_type",
    "url",
    "refusal_code",
    "refusal_reason",
    "manual_review_required",
    "production_ready",
    "approved_evidence",
    "refusal_root",
)
REFUSAL_CODES = (
    "REFUSED_MALFORMED_METADATA_PACK",
    "REFUSED_MALFORMED_METADATA_RECORD",
    "REFUSED_METADATA_HASH_MISMATCH",
    "REFUSED_METADATA_ROOT_MISMATCH",
    "REFUSED_DUPLICATE_METADATA_SOURCE_ID",
    "REFUSED_MALFORMED_INTAKE_TEMPLATE",
    "REFUSED_MALFORMED_INTAKE_RECORD",
    "REFUSED_DUPLICATE_INTAKE_SOURCE_ID",
    "REFUSED_MISSING_METADATA_RECORD",
    "REFUSED_SOURCE_ID_MISMATCH",
    "REFUSED_SLOT_IDENTITY_MISMATCH",
    "REFUSED_UNSPECIFIED_URL_NOT_ALLOWED",
)


class PopulateIntakeRefusal(ValueError):
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


def _metadata_hash_material(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: record[field]
        for field in METADATA_RECORD_FIELDS
        if field not in ("metadata_hash", "metadata_record_root")
    }


def _metadata_root_material(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: record[field]
        for field in METADATA_RECORD_FIELDS
        if field != "metadata_record_root"
    }


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    return {field: refusal[field] for field in REFUSAL_FIELDS if field != "refusal_root"}


def _require_nonempty_string(data: Dict[str, Any], field_name: str, code: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise PopulateIntakeRefusal(code, f"{field_name} must be a non-empty string.")


def _validate_metadata_record(record: Dict[str, Any]) -> None:
    if not isinstance(record, dict) or set(record.keys()) != set(METADATA_RECORD_FIELDS):
        raise PopulateIntakeRefusal(
            "REFUSED_MALFORMED_METADATA_RECORD",
            "Metadata record fields do not match expected schema.",
        )
    for field_name in METADATA_RECORD_FIELDS:
        if field_name == "manual_review_required":
            continue
        _require_nonempty_string(record, field_name, "REFUSED_MALFORMED_METADATA_RECORD")
    if record["time_direction"] not in TIME_DIRECTIONS:
        raise PopulateIntakeRefusal(
            "REFUSED_MALFORMED_METADATA_RECORD",
            f"Unsupported metadata time_direction: {record['time_direction']}.",
        )
    if record["source_type"] not in SOURCE_TYPES:
        raise PopulateIntakeRefusal(
            "REFUSED_MALFORMED_METADATA_RECORD",
            f"Unsupported metadata source_type: {record['source_type']}.",
        )
    if record["manual_review_required"] is not True:
        raise PopulateIntakeRefusal(
            "REFUSED_MALFORMED_METADATA_RECORD",
            "Metadata records must require manual review.",
        )
    if record["url"] == UNSPECIFIED_URL and record["source_id"] != ALLOWED_UNSPECIFIED_SOURCE_ID:
        raise PopulateIntakeRefusal(
            "REFUSED_UNSPECIFIED_URL_NOT_ALLOWED",
            "UNSPECIFIED URL is allowed only for the unresolved social media source.",
        )
    if record["metadata_hash"] != _hash_json(_metadata_hash_material(record)):
        raise PopulateIntakeRefusal(
            "REFUSED_METADATA_HASH_MISMATCH",
            f"metadata_hash mismatch for {record['source_id']}.",
        )
    if record["metadata_record_root"] != _hash_json(_metadata_root_material(record)):
        raise PopulateIntakeRefusal(
            "REFUSED_METADATA_ROOT_MISMATCH",
            f"metadata_record_root mismatch for {record['source_id']}.",
        )


def _load_metadata_records(metadata_pack_path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(metadata_pack_path)
    if not isinstance(payload, dict):
        raise ValueError("Temporal metadata pack must be a JSON object.")
    if payload.get("schema_version") != UPSTREAM_SCHEMA_VERSION:
        raise ValueError("Temporal metadata pack schema_version is unsupported.")
    records = payload.get("temporal_metadata_records")
    if not isinstance(records, list):
        raise ValueError("Temporal metadata pack must contain temporal_metadata_records list.")

    seen_source_ids = set()
    for record in records:
        _validate_metadata_record(record)
        source_id = record["source_id"]
        if source_id in seen_source_ids:
            raise PopulateIntakeRefusal(
                "REFUSED_DUPLICATE_METADATA_SOURCE_ID",
                f"Duplicate metadata source_id: {source_id}.",
            )
        seen_source_ids.add(source_id)
    return records


def _validate_intake_record(record: Dict[str, Any]) -> None:
    if not isinstance(record, dict) or set(record.keys()) != set(INTAKE_FIELDS):
        raise PopulateIntakeRefusal(
            "REFUSED_MALFORMED_INTAKE_RECORD",
            "Intake record fields do not match expected schema.",
        )
    for field_name in INTAKE_FIELDS:
        _require_nonempty_string(record, field_name, "REFUSED_MALFORMED_INTAKE_RECORD")
    if record["time_direction"] not in TIME_DIRECTIONS:
        raise PopulateIntakeRefusal(
            "REFUSED_MALFORMED_INTAKE_RECORD",
            f"Unsupported intake time_direction: {record['time_direction']}.",
        )
    if record["source_type"] not in SOURCE_TYPES:
        raise PopulateIntakeRefusal(
            "REFUSED_MALFORMED_INTAKE_RECORD",
            f"Unsupported intake source_type: {record['source_type']}.",
        )


def _load_intake_template(intake_template_path: Path) -> Dict[str, Any]:
    template = _load_json(intake_template_path)
    if not isinstance(template, dict):
        raise ValueError("Verified temporal URL intake template must be a JSON object.")
    expected_keys = {
        "generated_by",
        "intake_scope",
        "intake_version",
        "manual_review_required",
        "production_ready",
        "verified_temporal_url_intake",
    }
    if set(template.keys()) != expected_keys:
        raise ValueError("Verified temporal URL intake template wrapper keys changed.")
    if template.get("intake_version") != INTAKE_VERSION:
        raise ValueError("Verified temporal URL intake template version is unsupported.")
    if template.get("manual_review_required") is not True:
        raise ValueError("Verified temporal URL intake template manual_review_required must remain true.")
    if template.get("production_ready") is not False:
        raise ValueError("Verified temporal URL intake template production_ready must remain false.")
    records = template.get("verified_temporal_url_intake")
    if not isinstance(records, list):
        raise ValueError("Verified temporal URL intake template must contain intake list.")

    seen_source_ids = set()
    for record in records:
        _validate_intake_record(record)
        source_id = record["source_id"]
        if source_id in seen_source_ids:
            raise PopulateIntakeRefusal(
                "REFUSED_DUPLICATE_INTAKE_SOURCE_ID",
                f"Duplicate intake source_id: {source_id}.",
            )
        seen_source_ids.add(source_id)
    return template


def _make_refusal(
    sequence_number: int,
    source_id: str,
    time_direction: str,
    source_type: str,
    url: str,
    code: str,
    reason: str,
) -> Dict[str, Any]:
    refusal = {
        "populate_temporal_url_intake_refusal_id": f"POPULATE_TEMPORAL_URL_INTAKE_REFUSAL_{sequence_number:06d}",
        "source_id": source_id,
        "time_direction": time_direction,
        "source_type": source_type,
        "url": url,
        "refusal_code": code,
        "refusal_reason": reason,
        "manual_review_required": True,
        "production_ready": False,
        "approved_evidence": 0,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Populate refusal fields changed unexpectedly.")
    for field_name in REFUSAL_FIELDS:
        if field_name in ("manual_review_required", "production_ready", "approved_evidence"):
            continue
        value = refusal.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Populate refusal {field_name} must be non-empty.")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError("Populate refusal_code unsupported.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("Populate refusal manual_review_required must remain true.")
    if refusal["production_ready"] is not False:
        raise ValueError("Populate refusal production_ready must remain false.")
    if refusal["approved_evidence"] != 0:
        raise ValueError("Populate refusal approved_evidence must remain 0.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['source_id']}.")


def _metadata_map(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {record["source_id"]: record for record in records}


def _populate_template(
    template: Dict[str, Any],
    metadata_records: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    populated_template = copy.deepcopy(template)
    metadata_by_source_id = _metadata_map(metadata_records)
    updated_records: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []

    for record in populated_template["verified_temporal_url_intake"]:
        source_id = record["source_id"]
        metadata = metadata_by_source_id.get(source_id)
        if metadata is None:
            refusals.append(
                _make_refusal(
                    len(refusals) + 1,
                    source_id,
                    record["time_direction"],
                    record["source_type"],
                    record["url"],
                    "REFUSED_MISSING_METADATA_RECORD",
                    f"Missing metadata record for intake source_id {source_id}.",
                )
            )
            continue

        if metadata["source_id"] != source_id:
            refusals.append(
                _make_refusal(
                    len(refusals) + 1,
                    source_id,
                    record["time_direction"],
                    record["source_type"],
                    record["url"],
                    "REFUSED_SOURCE_ID_MISMATCH",
                    "Metadata source_id does not match intake source_id.",
                )
            )
            continue

        if (
            metadata["time_direction"] != record["time_direction"]
            or metadata["source_type"] != record["source_type"]
        ):
            refusals.append(
                _make_refusal(
                    len(refusals) + 1,
                    source_id,
                    record["time_direction"],
                    record["source_type"],
                    metadata["url"],
                    "REFUSED_SLOT_IDENTITY_MISMATCH",
                    "Metadata time_direction/source_type does not match intake slot identity.",
                )
            )
            continue

        if metadata["url"] == UNSPECIFIED_URL and source_id != ALLOWED_UNSPECIFIED_SOURCE_ID:
            refusals.append(
                _make_refusal(
                    len(refusals) + 1,
                    source_id,
                    record["time_direction"],
                    record["source_type"],
                    metadata["url"],
                    "REFUSED_UNSPECIFIED_URL_NOT_ALLOWED",
                    "UNSPECIFIED URL is allowed only for the unresolved social media source.",
                )
            )
            continue

        for field_name in COPIED_FIELDS:
            record[field_name] = metadata[field_name]
        updated_records.append(record)

    for refusal in refusals:
        validate_refusal(refusal)
    return populated_template, updated_records, refusals


def _status_for(mode: str, updated_count: int, refusal_count: int) -> str:
    if mode == "dry-run" and refusal_count == 0:
        return DRY_RUN_STATUS
    if mode == "apply" and updated_count > 0 and refusal_count == 0:
        return APPLIED_STATUS
    if updated_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _schema_payload() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "upstream_schema_version": UPSTREAM_SCHEMA_VERSION,
        "intake_version": INTAKE_VERSION,
        "metadata_record_fields": list(METADATA_RECORD_FIELDS),
        "intake_fields": list(INTAKE_FIELDS),
        "copied_fields": list(COPIED_FIELDS),
        "preserved_fields": list(PRESERVED_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "allowed_unspecified_url_source_id": ALLOWED_UNSPECIFIED_SOURCE_ID,
        "guardrails": {
            "approved_evidence": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "metadata_invented": 0,
            "production_ready": False,
            "quotes_created": 0,
            "timestamps_created": 0,
            "urls_invented": 0,
        },
    }


def _summary_root_material(summary: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {
        "populate_temporal_url_intake_root",
        "populate_temporal_url_intake_report_hash",
        "populate_temporal_url_intake_schema_hash",
    }
    return {key: value for key, value in summary.items() if key not in excluded}


def _build_report(
    status: str,
    mode: str,
    metadata_record_count: int,
    updated_records: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    updated_lines = ["- None"]
    if updated_records:
        updated_lines = []
        for record in updated_records[:20]:
            updated_lines.extend(
                [
                    f"- {record['source_id']}",
                    f"  - Direction: {record['time_direction']}",
                    f"  - Type: {record['source_type']}",
                    f"  - URL: {record['url']}",
                    f"  - Topic Preserved: {record['topic']}",
                ]
            )

    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['populate_temporal_url_intake_refusal_id']}: {refusal['refusal_code']}",
                    f"  - Source: {refusal['source_id']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )

    return "\n".join(
        [
            "# Populate Verified Temporal URL Intake v2",
            "",
            "This lane populates verified temporal URL intake records from the "
            "deep research metadata pack while preserving canonical slot identity. "
            "It does not validate URLs, invent URLs or metadata, create quotes, "
            "timestamps, claims, contradictions, production readiness, or approved evidence.",
            "",
            "## Summary",
            f"- populate_status: {status}",
            f"- mode: {mode}",
            f"- metadata_record_count: {metadata_record_count}",
            f"- updated_intake_record_count: {len(updated_records)}",
            f"- refusal_count: {len(refusals)}",
            f"- populate_temporal_url_intake_root: {root}",
            "",
            "## First Updated Intake Records",
            *updated_lines,
            "",
            "## First Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- URLs Invented: 0",
            "- Metadata Invented: 0",
            "- Quotes Created: 0",
            "- Timestamps Created: 0",
            "- Claims Created: 0",
            "- Contradictions Created: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "",
        ]
    )


def build_populate_verified_temporal_url_intake(
    mode: str = "dry-run",
    metadata_pack_path: Path = DEFAULT_METADATA_PACK,
    intake_template_path: Path = DEFAULT_INTAKE_TEMPLATE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "apply"):
        raise ValueError("mode must be 'dry-run' or 'apply'.")

    metadata_records = _load_metadata_records(metadata_pack_path)
    intake_template = _load_intake_template(intake_template_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    preview_template, updated_records, refusals = _populate_template(
        intake_template,
        metadata_records,
    )
    status = _status_for(mode, len(updated_records), len(refusals))
    schema = _schema_payload()
    schema_hash = _hash_json(schema)

    supplied_url_count = sum(
        1
        for record in preview_template["verified_temporal_url_intake"]
        if record["url"] != UNSPECIFIED_URL
    )
    unspecified_url_count = sum(
        1
        for record in preview_template["verified_temporal_url_intake"]
        if record["url"] == UNSPECIFIED_URL
    )
    topic_preserved_count = sum(
        1
        for before, after in zip(
            intake_template["verified_temporal_url_intake"],
            preview_template["verified_temporal_url_intake"],
        )
        if before["topic"] == after["topic"]
    )

    summary = {
        "populate_status": status,
        "mode": mode,
        "metadata_record_count": len(metadata_records),
        "intake_record_count": len(intake_template["verified_temporal_url_intake"]),
        "updated_intake_record_count": len(updated_records),
        "refusal_count": len(refusals),
        "supplied_url_count": supplied_url_count,
        "unspecified_url_count": unspecified_url_count,
        "topic_preserved_count": topic_preserved_count,
        "before_count": sum(1 for record in updated_records if record["time_direction"] == "BEFORE"),
        "after_count": sum(1 for record in updated_records if record["time_direction"] == "AFTER"),
        "refusal_roots": [refusal["refusal_root"] for refusal in refusals],
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "populate_temporal_url_intake_schema_hash": schema_hash,
        "populate_temporal_url_intake_report_hash": "",
        "populate_temporal_url_intake_root": "",
        "evidence_invented": 0,
        "urls_invented": 0,
        "metadata_invented": 0,
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
    summary["populate_temporal_url_intake_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(metadata_records),
        updated_records,
        refusals,
        summary["populate_temporal_url_intake_root"],
    )
    summary["populate_temporal_url_intake_report_hash"] = _sha256_text(report)
    summary["populate_temporal_url_intake_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(metadata_records),
        updated_records,
        refusals,
        summary["populate_temporal_url_intake_root"],
    )

    preview_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "populated_temporal_url_intake_preview": preview_template,
    }
    refusals_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "populate_temporal_url_intake_refusals": refusals,
    }

    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(output_dir / PREVIEW_OUTPUT.name, preview_payload)
    _write_json(output_dir / REFUSALS_OUTPUT.name, refusals_payload)
    _write_json(output_dir / SCHEMA_OUTPUT.name, schema)
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    if mode == "apply" and status in (APPLIED_STATUS, PARTIAL_STATUS):
        _write_json(intake_template_path, preview_template)

    return {
        "summary": summary,
        "populated_temporal_url_intake_preview": preview_template,
        "populate_temporal_url_intake_refusals": refusals,
        "schema": schema,
        "report": report,
    }


__all__ = ["build_populate_verified_temporal_url_intake"]
