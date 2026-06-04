#!/usr/bin/env python3
"""
Apply Validated Temporal URLs v2.

Applies only verified temporal URL intake records into the curated temporal
source pack. Refused intake URLs remain audit-only and are never applied. This
lane does not invent URLs or metadata, create quotes, timestamps, claims,
contradictions, production readiness, or approved evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple
import copy
import hashlib
import json


DEFAULT_VALIDATED_INTAKE = Path(
    "outputs/verified_temporal_url_intake/validated_temporal_url_intake.json"
)
DEFAULT_INTAKE_REFUSALS = Path(
    "outputs/verified_temporal_url_intake/temporal_url_intake_refusals.json"
)
DEFAULT_SOURCE_PACK = Path("inputs/temporal_sources/duma_boko_temporal_source_pack.json")
DEFAULT_OUTPUT_DIR = Path("outputs/apply_validated_temporal_urls")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "apply_validated_temporal_urls_summary.json"
APPLIED_OUTPUT = DEFAULT_OUTPUT_DIR / "applied_temporal_urls.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "apply_validated_temporal_url_refusals.json"
PREVIEW_OUTPUT = DEFAULT_OUTPUT_DIR / "updated_temporal_source_pack_preview.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "apply_validated_temporal_urls_report.md"

SCHEMA_VERSION = "apply_validated_temporal_urls_v2"
VALIDATED_INTAKE_SCHEMA_VERSION = "verified_temporal_url_intake_v2"

DRY_RUN_STATUS = "APPLY_VALIDATED_TEMPORAL_URLS_DRY_RUN_PREVIEW"
APPLIED_STATUS = "APPLY_VALIDATED_TEMPORAL_URLS_APPLIED"
PARTIAL_STATUS = "APPLY_VALIDATED_TEMPORAL_URLS_PARTIAL"
REFUSED_STATUS = "APPLY_VALIDATED_TEMPORAL_URLS_REFUSED"

INTAKE_VERIFICATION_STATUS = "VERIFIED_REACHABLE_TEMPORAL_URL_INTAKE"
SOURCE_PACK_VERIFICATION_STATUS = "VERIFIED_REACHABLE_TEMPORAL_SOURCE"
UNVERIFIED_SOURCE_STATUS = "UNVERIFIED_SOURCE_ENTRY"
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

VALIDATED_INTAKE_FIELDS = (
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
    "http_status",
    "content_type",
    "verification_status",
    "manual_review_required",
    "metadata_hash",
    "intake_root",
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
INTAKE_REFUSAL_FIELDS = (
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
APPLIED_URL_FIELDS = (
    "applied_temporal_url_id",
    "source_id",
    "time_direction",
    "source_type",
    "url",
    "title",
    "publisher",
    "published_date",
    "topic",
    "linked_claim_id",
    "notes",
    "http_status",
    "content_type",
    "source_pack_verification_status",
    "manual_review_required",
    "validated_intake_metadata_hash",
    "validated_intake_root",
    "applied_url_root",
)
APPLY_REFUSAL_FIELDS = (
    "apply_validated_temporal_url_refusal_id",
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
    "REFUSED_MALFORMED_VALIDATED_INTAKE",
    "REFUSED_VALIDATED_INTAKE_HASH_MISMATCH",
    "REFUSED_VALIDATED_INTAKE_ROOT_MISMATCH",
    "REFUSED_UNSUPPORTED_VERIFICATION_STATUS",
    "REFUSED_DUPLICATE_VALIDATED_SOURCE_ID",
    "REFUSED_MALFORMED_SOURCE_PACK",
    "REFUSED_DUPLICATE_SOURCE_PACK_ID",
    "REFUSED_MISSING_SOURCE_PACK_RECORD",
    "REFUSED_SLOT_IDENTITY_MISMATCH",
    "REFUSED_TOPIC_MISMATCH",
    "REFUSED_LINKED_CLAIM_MISMATCH",
)


class ApplyValidatedTemporalUrlRefusal(ValueError):
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


def _validated_metadata_material(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: record[field]
        for field in VALIDATED_INTAKE_FIELDS
        if field not in ("metadata_hash", "intake_root")
    }


def _validated_root_material(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: record[field]
        for field in VALIDATED_INTAKE_FIELDS
        if field != "intake_root"
    }


def _applied_root_material(record: Dict[str, Any]) -> Dict[str, Any]:
    return {field: record[field] for field in APPLIED_URL_FIELDS if field != "applied_url_root"}


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    return {field: refusal[field] for field in APPLY_REFUSAL_FIELDS if field != "refusal_root"}


def _intake_refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    return {field: refusal[field] for field in INTAKE_REFUSAL_FIELDS if field != "refusal_root"}


def _require_nonempty_string(data: Dict[str, Any], field_name: str, code: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ApplyValidatedTemporalUrlRefusal(code, f"{field_name} must be a non-empty string.")


def _validate_validated_intake(record: Dict[str, Any]) -> None:
    if not isinstance(record, dict) or set(record.keys()) != set(VALIDATED_INTAKE_FIELDS):
        raise ApplyValidatedTemporalUrlRefusal(
            "REFUSED_MALFORMED_VALIDATED_INTAKE",
            "Validated temporal URL intake record fields do not match schema.",
        )
    for field_name in VALIDATED_INTAKE_FIELDS:
        if field_name in ("http_status", "manual_review_required"):
            continue
        _require_nonempty_string(record, field_name, "REFUSED_MALFORMED_VALIDATED_INTAKE")
    if record["time_direction"] not in TIME_DIRECTIONS:
        raise ApplyValidatedTemporalUrlRefusal(
            "REFUSED_MALFORMED_VALIDATED_INTAKE",
            f"Unsupported time_direction: {record['time_direction']}.",
        )
    if record["source_type"] not in SOURCE_TYPES:
        raise ApplyValidatedTemporalUrlRefusal(
            "REFUSED_MALFORMED_VALIDATED_INTAKE",
            f"Unsupported source_type: {record['source_type']}.",
        )
    if record["verification_status"] != INTAKE_VERIFICATION_STATUS:
        raise ApplyValidatedTemporalUrlRefusal(
            "REFUSED_UNSUPPORTED_VERIFICATION_STATUS",
            f"Unsupported validated intake verification_status: {record['verification_status']}.",
        )
    if record["manual_review_required"] is not True:
        raise ApplyValidatedTemporalUrlRefusal(
            "REFUSED_MALFORMED_VALIDATED_INTAKE",
            "Validated temporal URL intake record must require manual review.",
        )
    if not isinstance(record["http_status"], int) or not (200 <= record["http_status"] < 400):
        raise ApplyValidatedTemporalUrlRefusal(
            "REFUSED_MALFORMED_VALIDATED_INTAKE",
            "Validated temporal URL intake http_status must be 200-399.",
        )
    if record["metadata_hash"] != _hash_json(_validated_metadata_material(record)):
        raise ApplyValidatedTemporalUrlRefusal(
            "REFUSED_VALIDATED_INTAKE_HASH_MISMATCH",
            f"metadata_hash mismatch for {record['source_id']}.",
        )
    if record["intake_root"] != _hash_json(_validated_root_material(record)):
        raise ApplyValidatedTemporalUrlRefusal(
            "REFUSED_VALIDATED_INTAKE_ROOT_MISMATCH",
            f"intake_root mismatch for {record['source_id']}.",
        )


def _load_validated_intake(validated_intake_path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(validated_intake_path)
    if not isinstance(payload, dict):
        raise ValueError("Validated temporal URL intake payload must be a JSON object.")
    if payload.get("schema_version") != VALIDATED_INTAKE_SCHEMA_VERSION:
        raise ValueError("Validated temporal URL intake schema_version is unsupported.")
    records = payload.get("validated_temporal_url_intake")
    if not isinstance(records, list):
        raise ValueError("Validated temporal URL intake payload must contain a list.")

    seen_source_ids = set()
    for record in records:
        _validate_validated_intake(record)
        source_id = record["source_id"]
        if source_id in seen_source_ids:
            raise ApplyValidatedTemporalUrlRefusal(
                "REFUSED_DUPLICATE_VALIDATED_SOURCE_ID",
                f"Duplicate validated intake source_id: {source_id}.",
            )
        seen_source_ids.add(source_id)
    return records


def _validate_source_pack_record(record: Dict[str, Any]) -> None:
    if not isinstance(record, dict) or set(record.keys()) != set(SOURCE_PACK_FIELDS):
        raise ApplyValidatedTemporalUrlRefusal(
            "REFUSED_MALFORMED_SOURCE_PACK",
            "Curated temporal source pack record fields do not match schema.",
        )
    for field_name in SOURCE_PACK_FIELDS:
        if field_name == "manual_review_required":
            continue
        _require_nonempty_string(record, field_name, "REFUSED_MALFORMED_SOURCE_PACK")
    if record["time_direction"] not in TIME_DIRECTIONS:
        raise ApplyValidatedTemporalUrlRefusal(
            "REFUSED_MALFORMED_SOURCE_PACK",
            f"Unsupported source pack time_direction: {record['time_direction']}.",
        )
    if record["source_type"] not in SOURCE_TYPES:
        raise ApplyValidatedTemporalUrlRefusal(
            "REFUSED_MALFORMED_SOURCE_PACK",
            f"Unsupported source pack source_type: {record['source_type']}.",
        )
    if record["manual_review_required"] is not True:
        raise ApplyValidatedTemporalUrlRefusal(
            "REFUSED_MALFORMED_SOURCE_PACK",
            "Curated temporal source pack entries must require manual review.",
        )


def _load_source_pack(source_pack_path: Path) -> Dict[str, Any]:
    pack = _load_json(source_pack_path)
    if not isinstance(pack, dict):
        raise ValueError("Curated temporal source pack must be a JSON object.")
    expected_keys = {
        "curated_temporal_sources",
        "generated_by",
        "manual_review_required",
        "pack_scope",
        "pack_version",
        "production_ready",
    }
    if set(pack.keys()) != expected_keys:
        raise ValueError("Curated temporal source pack wrapper keys changed.")
    if pack.get("manual_review_required") is not True:
        raise ValueError("Curated temporal source pack manual_review_required must remain true.")
    if pack.get("production_ready") is not False:
        raise ValueError("Curated temporal source pack production_ready must remain false.")
    sources = pack.get("curated_temporal_sources")
    if not isinstance(sources, list):
        raise ValueError("Curated temporal source pack must contain curated_temporal_sources list.")

    seen_source_ids = set()
    for source in sources:
        _validate_source_pack_record(source)
        source_id = source["source_id"]
        if source_id in seen_source_ids:
            raise ApplyValidatedTemporalUrlRefusal(
                "REFUSED_DUPLICATE_SOURCE_PACK_ID",
                f"Duplicate source pack source_id: {source_id}.",
            )
        seen_source_ids.add(source_id)
    return pack


def _load_intake_refusals(intake_refusals_path: Path) -> List[Dict[str, Any]]:
    if not intake_refusals_path.exists():
        return []
    payload = _load_json(intake_refusals_path)
    if not isinstance(payload, dict):
        raise ValueError("Temporal URL intake refusals payload must be a JSON object.")
    if payload.get("schema_version") != VALIDATED_INTAKE_SCHEMA_VERSION:
        raise ValueError("Temporal URL intake refusals schema_version is unsupported.")
    refusals = payload.get("temporal_url_intake_refusals")
    if not isinstance(refusals, list):
        raise ValueError("Temporal URL intake refusals payload must contain a list.")
    for refusal in refusals:
        if not isinstance(refusal, dict) or set(refusal.keys()) != set(INTAKE_REFUSAL_FIELDS):
            raise ValueError("Temporal URL intake refusal fields do not match schema.")
        if refusal["manual_review_required"] is not True:
            raise ValueError("Temporal URL intake refusal manual_review_required must remain true.")
        if refusal["refusal_root"] != _hash_json(_intake_refusal_root_material(refusal)):
            raise ValueError(f"Temporal URL intake refusal root mismatch for {refusal['source_id']}.")
    return refusals


def _make_apply_refusal(
    sequence_number: int,
    source_id: str,
    time_direction: str,
    source_type: str,
    url: str,
    code: str,
    reason: str,
) -> Dict[str, Any]:
    refusal = {
        "apply_validated_temporal_url_refusal_id": f"APPLY_VALIDATED_TEMPORAL_URL_REFUSAL_{sequence_number:06d}",
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


def validate_apply_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(APPLY_REFUSAL_FIELDS):
        raise ValueError("Apply validated temporal URL refusal fields changed unexpectedly.")
    for field_name in APPLY_REFUSAL_FIELDS:
        if field_name in ("manual_review_required", "production_ready", "approved_evidence"):
            continue
        value = refusal.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Apply refusal field {field_name} must be non-empty.")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError("Apply refusal_code unsupported.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("Apply refusal manual_review_required must remain true.")
    if refusal["production_ready"] is not False:
        raise ValueError("Apply refusal production_ready must remain false.")
    if refusal["approved_evidence"] != 0:
        raise ValueError("Apply refusal approved_evidence must remain 0.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"Apply refusal root mismatch for {refusal['source_id']}.")


def _make_applied_url(sequence_number: int, source: Dict[str, Any], intake: Dict[str, Any]) -> Dict[str, Any]:
    applied = {
        "applied_temporal_url_id": f"APPLIED_TEMPORAL_URL_{sequence_number:06d}",
        "source_id": source["source_id"],
        "time_direction": source["time_direction"],
        "source_type": source["source_type"],
        "url": source["url"],
        "title": source["title"],
        "publisher": source["publisher"],
        "published_date": source["published_date"],
        "topic": source["topic"],
        "linked_claim_id": source["linked_claim_id"],
        "notes": source["notes"],
        "http_status": intake["http_status"],
        "content_type": intake["content_type"],
        "source_pack_verification_status": source["verification_status"],
        "manual_review_required": True,
        "validated_intake_metadata_hash": intake["metadata_hash"],
        "validated_intake_root": intake["intake_root"],
        "applied_url_root": "",
    }
    applied["applied_url_root"] = _hash_json(_applied_root_material(applied))
    return applied


def validate_applied_url(applied: Dict[str, Any]) -> None:
    if set(applied.keys()) != set(APPLIED_URL_FIELDS):
        raise ValueError("Applied temporal URL fields changed unexpectedly.")
    for field_name in APPLIED_URL_FIELDS:
        if field_name in ("http_status", "manual_review_required"):
            continue
        value = applied.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Applied temporal URL field {field_name} must be non-empty.")
    if applied["source_pack_verification_status"] != SOURCE_PACK_VERIFICATION_STATUS:
        raise ValueError("Applied temporal URL source_pack_verification_status unsupported.")
    if applied["manual_review_required"] is not True:
        raise ValueError("Applied temporal URL manual_review_required must remain true.")
    if applied["applied_url_root"] != _hash_json(_applied_root_material(applied)):
        raise ValueError(f"Applied temporal URL root mismatch for {applied['source_id']}.")


def _apply_validated_records(
    source_pack: Dict[str, Any],
    validated_records: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    preview_pack = copy.deepcopy(source_pack)
    sources_by_id = {
        source["source_id"]: source
        for source in preview_pack["curated_temporal_sources"]
    }
    applied_urls: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []

    for intake in validated_records:
        source = sources_by_id.get(intake["source_id"])
        if source is None:
            refusals.append(
                _make_apply_refusal(
                    len(refusals) + 1,
                    intake["source_id"],
                    intake["time_direction"],
                    intake["source_type"],
                    intake["url"],
                    "REFUSED_MISSING_SOURCE_PACK_RECORD",
                    "Validated intake source_id is missing from curated temporal source pack.",
                )
            )
            continue

        if source["time_direction"] != intake["time_direction"] or source["source_type"] != intake["source_type"]:
            refusals.append(
                _make_apply_refusal(
                    len(refusals) + 1,
                    intake["source_id"],
                    intake["time_direction"],
                    intake["source_type"],
                    intake["url"],
                    "REFUSED_SLOT_IDENTITY_MISMATCH",
                    "Validated intake time_direction/source_type does not match source pack slot.",
                )
            )
            continue

        if source["topic"] != intake["topic"]:
            refusals.append(
                _make_apply_refusal(
                    len(refusals) + 1,
                    intake["source_id"],
                    intake["time_direction"],
                    intake["source_type"],
                    intake["url"],
                    "REFUSED_TOPIC_MISMATCH",
                    "Validated intake topic does not match canonical source pack topic.",
                )
            )
            continue

        if source["linked_claim_id"] != intake["linked_claim_id"]:
            refusals.append(
                _make_apply_refusal(
                    len(refusals) + 1,
                    intake["source_id"],
                    intake["time_direction"],
                    intake["source_type"],
                    intake["url"],
                    "REFUSED_LINKED_CLAIM_MISMATCH",
                    "Validated intake linked_claim_id does not match source pack slot.",
                )
            )
            continue

        source["url"] = intake["url"]
        source["title"] = intake["title"]
        source["publisher"] = intake["publisher"]
        source["published_date"] = intake["published_date"]
        source["verification_status"] = SOURCE_PACK_VERIFICATION_STATUS
        source["manual_review_required"] = True
        source["notes"] = intake["verification_notes"]
        applied_urls.append(_make_applied_url(len(applied_urls) + 1, source, intake))

    for applied in applied_urls:
        validate_applied_url(applied)
    for refusal in refusals:
        validate_apply_refusal(refusal)
    return preview_pack, applied_urls, refusals


def _status_for(mode: str, applied_count: int, refusal_count: int) -> str:
    if mode == "dry-run" and applied_count > 0 and refusal_count == 0:
        return DRY_RUN_STATUS
    if mode == "apply" and applied_count > 0 and refusal_count == 0:
        return APPLIED_STATUS
    if applied_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _summary_root_material(summary: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {
        "apply_validated_temporal_urls_root",
        "apply_validated_temporal_urls_report_hash",
    }
    return {key: value for key, value in summary.items() if key not in excluded}


def _build_report(
    status: str,
    mode: str,
    applied_urls: List[Dict[str, Any]],
    apply_refusals: List[Dict[str, Any]],
    intake_refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    applied_lines = ["- None"]
    if applied_urls:
        applied_lines = []
        for applied in applied_urls[:20]:
            applied_lines.extend(
                [
                    f"- {applied['applied_temporal_url_id']}",
                    f"  - Source: {applied['source_id']}",
                    f"  - URL: {applied['url']}",
                    f"  - Status: {applied['source_pack_verification_status']}",
                ]
            )

    refusal_lines = ["- None"]
    if apply_refusals:
        refusal_lines = []
        for refusal in apply_refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['apply_validated_temporal_url_refusal_id']}: {refusal['refusal_code']}",
                    f"  - Source: {refusal['source_id']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )

    intake_refusal_lines = ["- None"]
    if intake_refusals:
        intake_refusal_lines = []
        for refusal in intake_refusals[:20]:
            intake_refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Source: {refusal['source_id']}",
                ]
            )

    return "\n".join(
        [
            "# Apply Validated Temporal URLs v2",
            "",
            "This lane applies only validated temporal URL intake records into "
            "the curated temporal source pack. It does not apply refused URLs, "
            "invent URLs or metadata, create quotes, timestamps, claims, "
            "contradictions, production readiness, or approved evidence.",
            "",
            "## Summary",
            f"- apply_validated_temporal_urls_status: {status}",
            f"- mode: {mode}",
            f"- applied_url_count: {len(applied_urls)}",
            f"- apply_refusal_count: {len(apply_refusals)}",
            f"- intake_refused_url_count: {len(intake_refusals)}",
            f"- apply_validated_temporal_urls_root: {root}",
            "",
            "## First Applied URLs",
            *applied_lines,
            "",
            "## Apply Refusals",
            *refusal_lines,
            "",
            "## Intake Refusals Excluded From Apply",
            *intake_refusal_lines,
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


def build_apply_validated_temporal_urls(
    mode: str = "dry-run",
    validated_intake_path: Path = DEFAULT_VALIDATED_INTAKE,
    source_pack_path: Path = DEFAULT_SOURCE_PACK,
    intake_refusals_path: Path = DEFAULT_INTAKE_REFUSALS,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "apply"):
        raise ValueError("mode must be 'dry-run' or 'apply'.")

    validated_records = _load_validated_intake(validated_intake_path)
    source_pack = _load_source_pack(source_pack_path)
    intake_refusals = _load_intake_refusals(intake_refusals_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    preview_pack, applied_urls, apply_refusals = _apply_validated_records(
        source_pack,
        validated_records,
    )
    status = _status_for(mode, len(applied_urls), len(apply_refusals))

    summary = {
        "apply_validated_temporal_urls_status": status,
        "mode": mode,
        "validated_url_count": len(validated_records),
        "applied_url_count": len(applied_urls),
        "apply_refusal_count": len(apply_refusals),
        "refused_url_count": len(intake_refusals),
        "source_pack_record_count": len(source_pack["curated_temporal_sources"]),
        "preview_public_url_count": sum(
            1
            for source in preview_pack["curated_temporal_sources"]
            if source["url"] != UNSPECIFIED
        ),
        "preview_unspecified_url_count": sum(
            1
            for source in preview_pack["curated_temporal_sources"]
            if source["url"] == UNSPECIFIED
        ),
        "applied_source_ids": [applied["source_id"] for applied in applied_urls],
        "intake_refused_source_ids": [refusal["source_id"] for refusal in intake_refusals],
        "apply_refusal_roots": [refusal["refusal_root"] for refusal in apply_refusals],
        "applied_url_roots": [applied["applied_url_root"] for applied in applied_urls],
        "apply_validated_temporal_urls_report_hash": "",
        "apply_validated_temporal_urls_root": "",
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
    summary["apply_validated_temporal_urls_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        applied_urls,
        apply_refusals,
        intake_refusals,
        summary["apply_validated_temporal_urls_root"],
    )
    summary["apply_validated_temporal_urls_report_hash"] = _sha256_text(report)
    summary["apply_validated_temporal_urls_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        applied_urls,
        apply_refusals,
        intake_refusals,
        summary["apply_validated_temporal_urls_root"],
    )

    applied_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "applied_temporal_urls": applied_urls,
    }
    refusals_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "apply_validated_temporal_url_refusals": apply_refusals,
        "intake_refused_temporal_urls_excluded_from_apply": intake_refusals,
    }
    preview_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "updated_temporal_source_pack_preview": preview_pack,
    }

    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(output_dir / APPLIED_OUTPUT.name, applied_payload)
    _write_json(output_dir / REFUSALS_OUTPUT.name, refusals_payload)
    _write_json(output_dir / PREVIEW_OUTPUT.name, preview_payload)
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    if mode == "apply" and status in (APPLIED_STATUS, PARTIAL_STATUS):
        _write_json(source_pack_path, preview_pack)

    return {
        "summary": summary,
        "applied_temporal_urls": applied_urls,
        "apply_validated_temporal_url_refusals": apply_refusals,
        "updated_temporal_source_pack_preview": preview_pack,
        "report": report,
    }


__all__ = ["build_apply_validated_temporal_urls"]
