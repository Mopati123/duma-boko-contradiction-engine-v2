#!/usr/bin/env python3
"""
Verified Temporal URL Intake v2.

Validates human-supplied temporal URLs before the curated temporal source pack
is updated. This lane does not search the web, invent URLs, create quotes,
timestamps, claims, contradictions, production readiness, or approved evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse
import hashlib
import http.client
import json
import urllib.error
import urllib.request


DEFAULT_INTAKE_TEMPLATE = Path(
    "inputs/temporal_sources/verified_temporal_url_intake_template.json"
)
DEFAULT_CURATED_PACK = Path("inputs/temporal_sources/duma_boko_temporal_source_pack.json")
DEFAULT_OUTPUT_DIR = Path("outputs/verified_temporal_url_intake")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "verified_temporal_url_intake_summary.json"
VALIDATED_OUTPUT = DEFAULT_OUTPUT_DIR / "validated_temporal_url_intake.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_url_intake_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "verified_temporal_url_intake_report.md"

SCHEMA_VERSION = "verified_temporal_url_intake_v2"

DRY_RUN_STATUS = "VERIFIED_TEMPORAL_URL_INTAKE_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "VERIFIED_TEMPORAL_URL_INTAKE_CANDIDATE"
PARTIAL_STATUS = "VERIFIED_TEMPORAL_URL_INTAKE_PARTIAL"
REFUSED_STATUS = "VERIFIED_TEMPORAL_URL_INTAKE_REFUSED"

VERIFIED_STATUS = "VERIFIED_REACHABLE_TEMPORAL_URL_INTAKE"
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
CURATED_SOURCE_FIELDS = (
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
VALIDATED_INTAKE_FIELDS = (
    *INTAKE_FIELDS,
    "http_status",
    "content_type",
    "verification_status",
    "manual_review_required",
    "metadata_hash",
    "intake_root",
)
REFUSAL_FIELDS = (
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
REFUSAL_CODES = (
    "REFUSED_UNSPECIFIED_URL",
    "REFUSED_MALFORMED_INTAKE_RECORD",
    "REFUSED_DUPLICATE_SOURCE_ID",
    "REFUSED_UNKNOWN_SOURCE_ID",
    "REFUSED_SOURCE_SLOT_MISMATCH",
    "REFUSED_INVALID_URL",
    "REFUSED_SEARCH_RESULT_URL",
    "REFUSED_UNREACHABLE",
    "REFUSED_METADATA_UNVERIFIED",
    "REFUSED_INPUT_VALIDATION",
)


class IntakeValidationRefusal(ValueError):
    def __init__(self, code: str, reason: str, http_status: int = 0, content_type: str = ""):
        super().__init__(reason)
        self.code = code
        self.reason = reason
        self.http_status = http_status
        self.content_type = content_type


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
        raise IntakeValidationRefusal(
            "REFUSED_MALFORMED_INTAKE_RECORD",
            f"{object_name}.{field_name} must be a non-empty string.",
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


def _validated_metadata_material(validated: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: validated[field]
        for field in VALIDATED_INTAKE_FIELDS
        if field not in ("metadata_hash", "intake_root")
    }


def _validated_root_material(validated: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: validated[field]
        for field in VALIDATED_INTAKE_FIELDS
        if field != "intake_root"
    }


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    return {field: refusal[field] for field in REFUSAL_FIELDS if field != "refusal_root"}


def _validate_curated_source_record(source: Dict[str, Any]) -> None:
    if not isinstance(source, dict) or set(source.keys()) != set(CURATED_SOURCE_FIELDS):
        raise ValueError("Curated temporal source fields do not match expected schema.")
    for field_name in CURATED_SOURCE_FIELDS:
        if field_name == "manual_review_required":
            continue
        value = source.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Curated source {field_name} must be a non-empty string.")
    if source["time_direction"] not in TIME_DIRECTIONS:
        raise ValueError(f"Unsupported curated source time_direction: {source['time_direction']}.")
    if source["source_type"] not in SOURCE_TYPES:
        raise ValueError(f"Unsupported curated source source_type: {source['source_type']}.")
    if source["manual_review_required"] is not True:
        raise ValueError("Curated temporal source entries must require manual review.")


def _load_curated_source_map(curated_pack_path: Path) -> Dict[str, Dict[str, Any]]:
    pack = _load_json(curated_pack_path)
    if not isinstance(pack, dict):
        raise ValueError("Curated temporal source pack must be a JSON object.")
    if pack.get("production_ready") is not False:
        raise ValueError("Curated temporal source pack production_ready must remain false.")
    if pack.get("manual_review_required") is not True:
        raise ValueError("Curated temporal source pack manual_review_required must remain true.")
    sources = pack.get("curated_temporal_sources")
    if not isinstance(sources, list):
        raise ValueError("Curated temporal source pack must contain curated_temporal_sources list.")

    source_map: Dict[str, Dict[str, Any]] = {}
    for source in sources:
        _validate_curated_source_record(source)
        source_id = source["source_id"]
        if source_id in source_map:
            raise ValueError(f"Duplicate curated source_id: {source_id}.")
        source_map[source_id] = source
    return source_map


def _validate_template_shape(template: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(template, dict):
        raise ValueError("Verified temporal URL intake template must be a JSON object.")
    if template.get("production_ready") is not False:
        raise ValueError("Verified temporal URL intake template production_ready must remain false.")
    if template.get("manual_review_required") is not True:
        raise ValueError("Verified temporal URL intake template manual_review_required must remain true.")
    intake = template.get("verified_temporal_url_intake")
    if not isinstance(intake, list):
        raise ValueError("Verified temporal URL intake template must contain a list.")
    return intake


def _validate_intake_record_shape(record: Dict[str, Any]) -> None:
    if not isinstance(record, dict):
        raise IntakeValidationRefusal(
            "REFUSED_MALFORMED_INTAKE_RECORD",
            "Verified temporal URL intake record must be a JSON object.",
        )
    if set(record.keys()) != set(INTAKE_FIELDS):
        raise IntakeValidationRefusal(
            "REFUSED_MALFORMED_INTAKE_RECORD",
            "Verified temporal URL intake record fields do not match schema.",
        )
    for field_name in INTAKE_FIELDS:
        _require_nonempty_string(record, field_name, "VerifiedTemporalUrlIntake")
    if record["time_direction"] not in TIME_DIRECTIONS:
        raise IntakeValidationRefusal(
            "REFUSED_INPUT_VALIDATION",
            f"Unsupported time_direction: {record['time_direction']}.",
        )
    if record["source_type"] not in SOURCE_TYPES:
        raise IntakeValidationRefusal(
            "REFUSED_INPUT_VALIDATION",
            f"Unsupported source_type: {record['source_type']}.",
        )


def _validate_slot_mapping(record: Dict[str, Any], curated_source_map: Dict[str, Dict[str, Any]]) -> None:
    source_id = record["source_id"]
    curated_source = curated_source_map.get(source_id)
    if curated_source is None:
        raise IntakeValidationRefusal(
            "REFUSED_UNKNOWN_SOURCE_ID",
            f"Intake source_id does not exist in curated temporal source pack: {source_id}.",
        )
    for field_name in ("time_direction", "source_type", "topic", "linked_claim_id"):
        if record[field_name] != curated_source[field_name]:
            raise IntakeValidationRefusal(
                "REFUSED_SOURCE_SLOT_MISMATCH",
                f"Intake field {field_name} does not match curated temporal source slot.",
            )


def _fetch_url_metadata(url: str, method: str, timeout: int = 12) -> Tuple[int, str, str]:
    request = urllib.request.Request(
        url,
        method=method,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; DumaBokoContradictionEngine/2.0; "
                "verified-temporal-url-intake-only)"
            )
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), response.geturl(), response.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        content_type = exc.headers.get("content-type", "") if exc.headers else ""
        return int(exc.code), exc.geturl(), content_type
    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
        http.client.HTTPException,
        OSError,
    ) as exc:
        raise IntakeValidationRefusal(
            "REFUSED_UNREACHABLE",
            f"Unable to fetch supplied URL metadata: {exc}",
        ) from exc


def _validate_supplied_url(record: Dict[str, Any]) -> Tuple[int, str]:
    url = record["url"].strip()
    if url == UNSPECIFIED:
        raise IntakeValidationRefusal(
            "REFUSED_UNSPECIFIED_URL",
            "Verified temporal URL intake record URL is UNSPECIFIED.",
        )
    if not _is_public_url(url):
        raise IntakeValidationRefusal(
            "REFUSED_INVALID_URL",
            "Verified temporal URL intake record URL must be public HTTP(S).",
        )
    if _is_generic_search_url(url):
        raise IntakeValidationRefusal(
            "REFUSED_SEARCH_RESULT_URL",
            "Search-result pages cannot be validated as temporal source URLs.",
        )
    for field_name in ("title", "publisher", "published_date", "topic", "verification_notes"):
        if record[field_name].strip() == UNSPECIFIED:
            raise IntakeValidationRefusal(
                "REFUSED_METADATA_UNVERIFIED",
                f"Supplied URL entries require non-UNSPECIFIED {field_name}.",
            )

    status, resolved_url, content_type = _fetch_url_metadata(url, "HEAD")
    if status in (0, 405, 403) or not content_type:
        status, resolved_url, content_type = _fetch_url_metadata(url, "GET")
    if status < 200 or status >= 400:
        raise IntakeValidationRefusal(
            "REFUSED_UNREACHABLE",
            f"HTTP status {status} is outside 200-399.",
            http_status=status,
            content_type=content_type,
        )
    if not content_type.strip():
        raise IntakeValidationRefusal(
            "REFUSED_METADATA_UNVERIFIED",
            "Supplied URL content_type is empty.",
            http_status=status,
            content_type=content_type,
        )
    if _is_generic_search_url(resolved_url):
        raise IntakeValidationRefusal(
            "REFUSED_SEARCH_RESULT_URL",
            "Supplied URL resolved to a search-result page.",
            http_status=status,
            content_type=content_type,
        )
    return status, content_type


def _make_validated_intake(
    sequence_number: int,
    record: Dict[str, Any],
    http_status: int,
    content_type: str,
) -> Dict[str, Any]:
    validated = {
        "source_id": record["source_id"],
        "time_direction": record["time_direction"],
        "source_type": record["source_type"],
        "url": record["url"],
        "title": record["title"],
        "publisher": record["publisher"],
        "published_date": record["published_date"],
        "topic": record["topic"],
        "linked_claim_id": record["linked_claim_id"],
        "verification_notes": record["verification_notes"],
        "http_status": http_status,
        "content_type": content_type,
        "verification_status": VERIFIED_STATUS,
        "manual_review_required": True,
        "metadata_hash": "",
        "intake_root": "",
    }
    _ = sequence_number
    validated["metadata_hash"] = _hash_json(_validated_metadata_material(validated))
    validated["intake_root"] = _hash_json(_validated_root_material(validated))
    return validated


def _source_stub(record: Any) -> Dict[str, str]:
    if not isinstance(record, dict):
        return {
            "source_id": "UNKNOWN_SOURCE_ID",
            "time_direction": "UNSPECIFIED",
            "source_type": "UNSPECIFIED",
            "url": "UNSPECIFIED",
        }
    return {
        "source_id": str(record.get("source_id") or "UNKNOWN_SOURCE_ID"),
        "time_direction": str(record.get("time_direction") or "UNSPECIFIED"),
        "source_type": str(record.get("source_type") or "UNSPECIFIED"),
        "url": str(record.get("url") or "UNSPECIFIED"),
    }


def _make_refusal(
    sequence_number: int,
    record: Any,
    code: str,
    reason: str,
) -> Dict[str, Any]:
    stub = _source_stub(record)
    refusal = {
        "refusal_id": f"TEMPORAL_URL_INTAKE_REFUSAL_{sequence_number:06d}",
        "source_id": stub["source_id"],
        "time_direction": stub["time_direction"],
        "source_type": stub["source_type"],
        "url": stub["url"],
        "refusal_code": code,
        "refusal_reason": reason,
        "manual_review_required": True,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_validated_intake(validated: Dict[str, Any]) -> None:
    if set(validated.keys()) != set(VALIDATED_INTAKE_FIELDS):
        raise ValueError("Validated temporal URL intake fields changed unexpectedly.")
    for field_name in VALIDATED_INTAKE_FIELDS:
        if field_name in ("http_status", "manual_review_required"):
            continue
        value = validated.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"ValidatedTemporalUrlIntake.{field_name} must be non-empty.")
    if validated["time_direction"] not in TIME_DIRECTIONS:
        raise ValueError("ValidatedTemporalUrlIntake.time_direction unsupported.")
    if validated["source_type"] not in SOURCE_TYPES:
        raise ValueError("ValidatedTemporalUrlIntake.source_type unsupported.")
    if not _is_public_url(validated["url"]):
        raise ValueError("ValidatedTemporalUrlIntake.url must be public HTTP(S).")
    if _is_generic_search_url(validated["url"]):
        raise ValueError("ValidatedTemporalUrlIntake.url cannot be a search-result page.")
    if not isinstance(validated["http_status"], int) or not (200 <= validated["http_status"] < 400):
        raise ValueError("ValidatedTemporalUrlIntake.http_status must be 200-399.")
    if validated["verification_status"] != VERIFIED_STATUS:
        raise ValueError("ValidatedTemporalUrlIntake.verification_status unsupported.")
    if validated["manual_review_required"] is not True:
        raise ValueError("ValidatedTemporalUrlIntake.manual_review_required must remain true.")
    if validated["metadata_hash"] != _hash_json(_validated_metadata_material(validated)):
        raise ValueError(f"metadata_hash mismatch for {validated['source_id']}.")
    if validated["intake_root"] != _hash_json(_validated_root_material(validated)):
        raise ValueError(f"intake_root mismatch for {validated['source_id']}.")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Temporal URL intake refusal fields changed unexpectedly.")
    for field_name in REFUSAL_FIELDS:
        if field_name == "manual_review_required":
            continue
        value = refusal.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"TemporalUrlIntakeRefusal.{field_name} must be non-empty.")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError("TemporalUrlIntakeRefusal.refusal_code unsupported.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("TemporalUrlIntakeRefusal.manual_review_required must remain true.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['source_id']}.")


def _build_validated_and_refusals(
    intake_records: List[Dict[str, Any]],
    curated_source_map: Dict[str, Dict[str, Any]],
    mode: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    validated_records: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    valid_shape_records: List[Dict[str, Any]] = []
    seen_source_ids = set()

    for record in intake_records:
        try:
            _validate_intake_record_shape(record)
            if record["source_id"] in seen_source_ids:
                raise IntakeValidationRefusal(
                    "REFUSED_DUPLICATE_SOURCE_ID",
                    f"Duplicate intake source_id: {record['source_id']}.",
                )
            seen_source_ids.add(record["source_id"])
            _validate_slot_mapping(record, curated_source_map)
            valid_shape_records.append(record)
            if mode == "validate-intake":
                http_status, content_type = _validate_supplied_url(record)
                validated_records.append(
                    _make_validated_intake(
                        len(validated_records) + 1,
                        record,
                        http_status,
                        content_type,
                    )
                )
        except IntakeValidationRefusal as exc:
            if mode == "validate-intake":
                refusals.append(_make_refusal(len(refusals) + 1, record, exc.code, exc.reason))
            else:
                raise

    for validated in validated_records:
        validate_validated_intake(validated)
    for refusal in refusals:
        validate_refusal(refusal)
    return validated_records, refusals, valid_shape_records


def _status_for(mode: str, validated_count: int, refusal_count: int) -> str:
    if mode == "dry-run" and refusal_count == 0:
        return DRY_RUN_STATUS
    if validated_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if validated_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _summary_root_material(summary: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {
        "verified_temporal_url_intake_root",
        "verified_temporal_url_intake_report_hash",
    }
    return {key: value for key, value in summary.items() if key not in excluded}


def _build_report(
    status: str,
    mode: str,
    input_count: int,
    validated_records: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    validated_lines = ["- None"]
    if validated_records:
        validated_lines = []
        for validated in validated_records[:20]:
            validated_lines.extend(
                [
                    f"- {validated['source_id']}",
                    f"  - URL: {validated['url']}",
                    f"  - HTTP Status: {validated['http_status']}",
                    f"  - Verification Status: {validated['verification_status']}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Source: {refusal['source_id']}",
                    f"  - URL: {refusal['url']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Verified Temporal URL Intake v2",
            "",
            "This lane validates human-supplied temporal URLs only. It does not "
            "search the web, invent URLs, create quotes, timestamps, claims, "
            "contradictions, production readiness, or approved evidence.",
            "",
            "## Summary",
            f"- intake_status: {status}",
            f"- mode: {mode}",
            f"- input_url_count: {input_count}",
            f"- validated_url_count: {len(validated_records)}",
            f"- refusal_count: {len(refusals)}",
            f"- verified_temporal_url_intake_root: {root}",
            "",
            "## First Validated URLs",
            *validated_lines,
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


def build_verified_temporal_url_intake(
    mode: str = "dry-run",
    intake_template_path: Path = DEFAULT_INTAKE_TEMPLATE,
    curated_pack_path: Path = DEFAULT_CURATED_PACK,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "validate-intake"):
        raise ValueError("mode must be 'dry-run' or 'validate-intake'.")

    curated_source_map = _load_curated_source_map(curated_pack_path)
    template = _load_json(intake_template_path)
    intake_records = _validate_template_shape(template)
    output_dir.mkdir(parents=True, exist_ok=True)

    validated_records, refusals, valid_shape_records = _build_validated_and_refusals(
        intake_records,
        curated_source_map,
        mode,
    )
    count_basis = valid_shape_records
    status = _status_for(mode, len(validated_records), len(refusals))

    summary = {
        "intake_status": status,
        "mode": mode,
        "input_url_count": len(intake_records),
        "validatable_intake_count": len(count_basis),
        "validated_url_count": len(validated_records),
        "refusal_count": len(refusals),
        "before_source_count": sum(1 for record in count_basis if record["time_direction"] == "BEFORE"),
        "after_source_count": sum(1 for record in count_basis if record["time_direction"] == "AFTER"),
        "unspecified_url_count": sum(1 for record in count_basis if record["url"] == UNSPECIFIED),
        "public_url_input_count": sum(1 for record in count_basis if _is_public_url(record["url"])),
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "metadata_hashes": [record["metadata_hash"] for record in validated_records],
        "intake_roots": [record["intake_root"] for record in validated_records],
        "refusal_roots": [refusal["refusal_root"] for refusal in refusals],
        "verified_temporal_url_intake_report_hash": "",
        "verified_temporal_url_intake_root": "",
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
    summary["verified_temporal_url_intake_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(intake_records),
        validated_records,
        refusals,
        summary["verified_temporal_url_intake_root"],
    )
    summary["verified_temporal_url_intake_report_hash"] = _sha256_text(report)
    summary["verified_temporal_url_intake_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(intake_records),
        validated_records,
        refusals,
        summary["verified_temporal_url_intake_root"],
    )

    validated_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "validated_temporal_url_intake": validated_records,
    }
    refusals_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "temporal_url_intake_refusals": refusals,
    }

    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(output_dir / VALIDATED_OUTPUT.name, validated_payload)
    _write_json(output_dir / REFUSALS_OUTPUT.name, refusals_payload)
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    return {
        "summary": summary,
        "validated_temporal_url_intake": validated_records,
        "temporal_url_intake_refusals": refusals,
        "report": report,
    }


__all__ = ["build_verified_temporal_url_intake"]
