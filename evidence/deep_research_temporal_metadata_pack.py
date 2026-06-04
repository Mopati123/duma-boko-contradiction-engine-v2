#!/usr/bin/env python3
"""
Deep Research Temporal Metadata Pack v2.

Extracts a reviewable metadata pack from a completed deep research temporal
URL candidate artifact. This lane does not modify intake templates, validate
URLs, invent URLs or metadata, create quotes, timestamps, claims,
contradictions, production readiness, or approved evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse
import hashlib
import json


DEFAULT_INPUT_CANDIDATES = Path(
    "inputs/temporal_sources/deep_research_temporal_url_candidates.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/deep_research_temporal_metadata_pack")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_metadata_pack_summary.json"
PACK_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_metadata_pack.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_metadata_pack_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_metadata_pack_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_metadata_pack_schema.json"

SCHEMA_VERSION = "deep_research_temporal_metadata_pack_v2"

DRY_RUN_STATUS = "TEMPORAL_METADATA_PACK_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "TEMPORAL_METADATA_PACK_CANDIDATE"
PARTIAL_STATUS = "TEMPORAL_METADATA_PACK_PARTIAL"
REFUSED_STATUS = "TEMPORAL_METADATA_PACK_REFUSED"

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

CANDIDATE_FIELDS = (
    "source_id",
    "title",
    "publisher",
    "published_date",
    "source_type",
    "time_direction",
    "topic",
    "verification_notes",
    "url",
)
METADATA_RECORD_FIELDS = (
    *CANDIDATE_FIELDS,
    "manual_review_required",
    "metadata_hash",
    "metadata_record_root",
)
REFUSAL_FIELDS = (
    "temporal_metadata_pack_refusal_id",
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
    "REFUSED_MALFORMED_CANDIDATE_RECORD",
    "REFUSED_DUPLICATE_SOURCE_ID",
    "REFUSED_UNSUPPORTED_TIME_DIRECTION",
    "REFUSED_UNSUPPORTED_SOURCE_TYPE",
    "REFUSED_UNSPECIFIED_URL_NOT_ALLOWED",
    "REFUSED_INVALID_PUBLIC_URL",
)


class MetadataPackRefusal(ValueError):
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


def _is_public_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _metadata_material(record: Dict[str, Any]) -> Dict[str, Any]:
    return {field: record[field] for field in CANDIDATE_FIELDS}


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


def _validate_artifact_shape(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("Deep research temporal URL candidate artifact must be a JSON object.")
    if set(payload.keys()) != {"candidates"}:
        raise ValueError("Deep research artifact must contain only the top-level candidates key.")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("Deep research artifact candidates value must be a list.")
    return candidates


def _require_nonempty_string(candidate: Dict[str, Any], field_name: str) -> None:
    value = candidate.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise MetadataPackRefusal(
            "REFUSED_MALFORMED_CANDIDATE_RECORD",
            f"Candidate field {field_name} must be a non-empty string.",
        )


def _validate_candidate_record(candidate: Dict[str, Any]) -> None:
    if not isinstance(candidate, dict):
        raise MetadataPackRefusal(
            "REFUSED_MALFORMED_CANDIDATE_RECORD",
            "Candidate record must be a JSON object.",
        )
    if set(candidate.keys()) != set(CANDIDATE_FIELDS):
        raise MetadataPackRefusal(
            "REFUSED_MALFORMED_CANDIDATE_RECORD",
            "Candidate record fields do not match the required metadata schema.",
        )
    for field_name in CANDIDATE_FIELDS:
        _require_nonempty_string(candidate, field_name)
    if candidate["time_direction"] not in TIME_DIRECTIONS:
        raise MetadataPackRefusal(
            "REFUSED_UNSUPPORTED_TIME_DIRECTION",
            f"Unsupported time_direction: {candidate['time_direction']}.",
        )
    if candidate["source_type"] not in SOURCE_TYPES:
        raise MetadataPackRefusal(
            "REFUSED_UNSUPPORTED_SOURCE_TYPE",
            f"Unsupported source_type: {candidate['source_type']}.",
        )

    url = candidate["url"].strip()
    if url == UNSPECIFIED_URL:
        if candidate["source_id"] != ALLOWED_UNSPECIFIED_SOURCE_ID:
            raise MetadataPackRefusal(
                "REFUSED_UNSPECIFIED_URL_NOT_ALLOWED",
                "UNSPECIFIED URL is allowed only for the unresolved social media source.",
            )
        return
    if not _is_public_url(url):
        raise MetadataPackRefusal(
            "REFUSED_INVALID_PUBLIC_URL",
            "Candidate URL must be public HTTP(S) or the allowed UNSPECIFIED social media URL.",
        )


def _make_metadata_record(candidate: Dict[str, Any]) -> Dict[str, Any]:
    record = {
        "source_id": candidate["source_id"],
        "title": candidate["title"],
        "publisher": candidate["publisher"],
        "published_date": candidate["published_date"],
        "source_type": candidate["source_type"],
        "time_direction": candidate["time_direction"],
        "topic": candidate["topic"],
        "verification_notes": candidate["verification_notes"],
        "url": candidate["url"],
        "manual_review_required": True,
        "metadata_hash": "",
        "metadata_record_root": "",
    }
    record["metadata_hash"] = _hash_json(_metadata_hash_material(record))
    record["metadata_record_root"] = _hash_json(_metadata_root_material(record))
    return record


def _candidate_stub(candidate: Any) -> Dict[str, str]:
    if not isinstance(candidate, dict):
        return {
            "source_id": "UNKNOWN_SOURCE_ID",
            "time_direction": "UNSPECIFIED",
            "source_type": "UNSPECIFIED",
            "url": "UNSPECIFIED",
        }
    return {
        "source_id": str(candidate.get("source_id") or "UNKNOWN_SOURCE_ID"),
        "time_direction": str(candidate.get("time_direction") or "UNSPECIFIED"),
        "source_type": str(candidate.get("source_type") or "UNSPECIFIED"),
        "url": str(candidate.get("url") or "UNSPECIFIED"),
    }


def _make_refusal(
    sequence_number: int,
    candidate: Any,
    code: str,
    reason: str,
) -> Dict[str, Any]:
    stub = _candidate_stub(candidate)
    refusal = {
        "temporal_metadata_pack_refusal_id": f"TEMPORAL_METADATA_PACK_REFUSAL_{sequence_number:06d}",
        "source_id": stub["source_id"],
        "time_direction": stub["time_direction"],
        "source_type": stub["source_type"],
        "url": stub["url"],
        "refusal_code": code,
        "refusal_reason": reason,
        "manual_review_required": True,
        "production_ready": False,
        "approved_evidence": 0,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_metadata_record(record: Dict[str, Any]) -> None:
    if set(record.keys()) != set(METADATA_RECORD_FIELDS):
        raise ValueError("Metadata record fields changed unexpectedly.")
    for field_name in METADATA_RECORD_FIELDS:
        if field_name == "manual_review_required":
            continue
        value = record.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Metadata record field {field_name} must be non-empty.")
    if record["time_direction"] not in TIME_DIRECTIONS:
        raise ValueError("Metadata record time_direction unsupported.")
    if record["source_type"] not in SOURCE_TYPES:
        raise ValueError("Metadata record source_type unsupported.")
    if record["manual_review_required"] is not True:
        raise ValueError("Metadata record manual_review_required must remain true.")
    if record["url"] == UNSPECIFIED_URL and record["source_id"] != ALLOWED_UNSPECIFIED_SOURCE_ID:
        raise ValueError("Metadata record contains disallowed UNSPECIFIED URL.")
    if record["url"] != UNSPECIFIED_URL and not _is_public_url(record["url"]):
        raise ValueError("Metadata record URL must be public HTTP(S).")
    if record["metadata_hash"] != _hash_json(_metadata_hash_material(record)):
        raise ValueError(f"metadata_hash mismatch for {record['source_id']}.")
    if record["metadata_record_root"] != _hash_json(_metadata_root_material(record)):
        raise ValueError(f"metadata_record_root mismatch for {record['source_id']}.")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Metadata pack refusal fields changed unexpectedly.")
    for field_name in REFUSAL_FIELDS:
        if field_name in ("manual_review_required", "production_ready", "approved_evidence"):
            continue
        value = refusal.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Metadata refusal field {field_name} must be non-empty.")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError("Metadata pack refusal_code unsupported.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("Metadata pack refusal manual_review_required must remain true.")
    if refusal["production_ready"] is not False:
        raise ValueError("Metadata pack refusal production_ready must remain false.")
    if refusal["approved_evidence"] != 0:
        raise ValueError("Metadata pack refusal approved_evidence must remain 0.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['source_id']}.")


def _build_metadata_and_refusals(
    candidates: List[Dict[str, Any]],
    mode: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    metadata_records: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    valid_candidates: List[Dict[str, Any]] = []
    seen_source_ids = set()

    for candidate in candidates:
        try:
            _validate_candidate_record(candidate)
            source_id = candidate["source_id"]
            if source_id in seen_source_ids:
                raise MetadataPackRefusal(
                    "REFUSED_DUPLICATE_SOURCE_ID",
                    f"Duplicate source_id: {source_id}.",
                )
            seen_source_ids.add(source_id)
            valid_candidates.append(candidate)
            if mode == "extract-pack":
                metadata_records.append(_make_metadata_record(candidate))
        except MetadataPackRefusal as exc:
            refusals.append(_make_refusal(len(refusals) + 1, candidate, exc.code, exc.reason))

    for record in metadata_records:
        validate_metadata_record(record)
    for refusal in refusals:
        validate_refusal(refusal)
    return metadata_records, refusals, valid_candidates


def _status_for(mode: str, metadata_count: int, refusal_count: int) -> str:
    if mode == "dry-run" and refusal_count == 0:
        return DRY_RUN_STATUS
    if metadata_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if metadata_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _schema_payload() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "input_candidate_fields": list(CANDIDATE_FIELDS),
        "metadata_record_fields": list(METADATA_RECORD_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "allowed_time_direction": list(TIME_DIRECTIONS),
        "allowed_source_type": list(SOURCE_TYPES),
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
        "temporal_metadata_pack_root",
        "temporal_metadata_pack_report_hash",
        "temporal_metadata_pack_schema_hash",
    }
    return {key: value for key, value in summary.items() if key not in excluded}


def _build_report(
    status: str,
    mode: str,
    candidate_count: int,
    metadata_records: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    metadata_lines = ["- None"]
    if metadata_records:
        metadata_lines = []
        for record in metadata_records[:20]:
            metadata_lines.extend(
                [
                    f"- {record['source_id']}",
                    f"  - Direction: {record['time_direction']}",
                    f"  - Type: {record['source_type']}",
                    f"  - URL: {record['url']}",
                    f"  - Metadata Hash: {record['metadata_hash']}",
                ]
            )

    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['temporal_metadata_pack_refusal_id']}: {refusal['refusal_code']}",
                    f"  - Source: {refusal['source_id']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )

    return "\n".join(
        [
            "# Deep Research Temporal Metadata Pack v2",
            "",
            "This lane extracts a reviewable metadata pack from the completed "
            "deep research temporal URL candidate artifact. It does not modify "
            "intake templates, validate URLs, invent URLs or metadata, create "
            "quotes, timestamps, claims, contradictions, production readiness, "
            "or approved evidence.",
            "",
            "## Summary",
            f"- temporal_metadata_pack_status: {status}",
            f"- mode: {mode}",
            f"- candidate_count: {candidate_count}",
            f"- metadata_record_count: {len(metadata_records)}",
            f"- refusal_count: {len(refusals)}",
            f"- temporal_metadata_pack_root: {root}",
            "",
            "## First Metadata Records",
            *metadata_lines,
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


def build_deep_research_temporal_metadata_pack(
    mode: str = "dry-run",
    input_candidates_path: Path = DEFAULT_INPUT_CANDIDATES,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "extract-pack"):
        raise ValueError("mode must be 'dry-run' or 'extract-pack'.")

    payload = _load_json(input_candidates_path)
    candidates = _validate_artifact_shape(payload)
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata_records, refusals, valid_candidates = _build_metadata_and_refusals(
        candidates,
        mode,
    )
    count_basis = valid_candidates
    status = _status_for(mode, len(metadata_records), len(refusals))
    schema = _schema_payload()
    schema_hash = _hash_json(schema)

    summary = {
        "temporal_metadata_pack_status": status,
        "mode": mode,
        "candidate_count": len(candidates),
        "valid_candidate_count": len(count_basis),
        "before_count": sum(1 for candidate in count_basis if candidate["time_direction"] == "BEFORE"),
        "after_count": sum(1 for candidate in count_basis if candidate["time_direction"] == "AFTER"),
        "metadata_record_count": len(metadata_records),
        "refusal_count": len(refusals),
        "unspecified_url_count": sum(1 for candidate in count_basis if candidate["url"] == UNSPECIFIED_URL),
        "public_url_count": sum(1 for candidate in count_basis if _is_public_url(candidate["url"])),
        "manual_review_required_count": len(metadata_records),
        "metadata_hashes": [record["metadata_hash"] for record in metadata_records],
        "metadata_record_roots": [record["metadata_record_root"] for record in metadata_records],
        "refusal_roots": [refusal["refusal_root"] for refusal in refusals],
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "temporal_metadata_pack_schema_hash": schema_hash,
        "temporal_metadata_pack_report_hash": "",
        "temporal_metadata_pack_root": "",
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
    summary["temporal_metadata_pack_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(candidates),
        metadata_records,
        refusals,
        summary["temporal_metadata_pack_root"],
    )
    summary["temporal_metadata_pack_report_hash"] = _sha256_text(report)
    summary["temporal_metadata_pack_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(candidates),
        metadata_records,
        refusals,
        summary["temporal_metadata_pack_root"],
    )

    pack_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "temporal_metadata_records": metadata_records,
    }
    refusals_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "temporal_metadata_pack_refusals": refusals,
    }

    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(output_dir / PACK_OUTPUT.name, pack_payload)
    _write_json(output_dir / REFUSALS_OUTPUT.name, refusals_payload)
    _write_json(output_dir / SCHEMA_OUTPUT.name, schema)
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    return {
        "summary": summary,
        "temporal_metadata_records": metadata_records,
        "temporal_metadata_pack_refusals": refusals,
        "schema": schema,
        "report": report,
    }


__all__ = ["build_deep_research_temporal_metadata_pack"]
