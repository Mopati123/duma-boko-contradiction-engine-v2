#!/usr/bin/env python3
"""
AFTER-Source Candidate Intake v2.

Validates human-supplied AFTER candidate URLs against temporal after-source
stability targets. This lane does not invent URLs, search the web, modify the
temporal source pack, create claims, create contradictions, create proof chains,
mark production readiness, or approve evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse
import hashlib
import http.client
import json
import urllib.error
import urllib.request


DEFAULT_TARGETS = Path(
    "outputs/temporal_after_source_stability_expansion/"
    "temporal_after_source_stability_targets.json"
)
DEFAULT_TEMPLATE = Path(
    "inputs/temporal_sources/after_source_candidate_intake_template.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/after_source_candidate_intake")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "after_source_candidate_intake_summary.json"
VALIDATED_OUTPUT = DEFAULT_OUTPUT_DIR / "validated_after_source_candidates.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "after_source_candidate_intake_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "after_source_candidate_intake_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "after_source_candidate_intake_schema.json"

SCHEMA_VERSION = "after_source_candidate_intake_v2"
TARGET_SCHEMA_VERSION = "temporal_after_source_stability_expansion_v2"

DRY_RUN_STATUS = "AFTER_SOURCE_CANDIDATE_INTAKE_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "AFTER_SOURCE_CANDIDATE_INTAKE_CANDIDATE"
PARTIAL_STATUS = "AFTER_SOURCE_CANDIDATE_INTAKE_PARTIAL"
REFUSED_STATUS = "AFTER_SOURCE_CANDIDATE_INTAKE_REFUSED"

VERIFIED_STATUS = "VERIFIED_REACHABLE_AFTER_SOURCE_CANDIDATE"
UNSPECIFIED = "UNSPECIFIED"

TARGET_THEMES = (
    "job creation / 500,000 jobs",
    "P4000 living wage",
    "education delivery",
    "sport funding",
    "economic growth",
    "energy / solar project",
    "official government delivery status",
    "budget / parliament / ministry follow-up",
)
TARGET_EVIDENCE_TYPES = (
    "OFFICIAL_GOVERNMENT_STATUS",
    "MINISTRY_UPDATE",
    "BUDGET_ACTION",
    "PARLIAMENT_RECORD",
    "NEWS_FOLLOWUP",
)
PREFERRED_SOURCE_FAMILIES = (
    "GOV_BW",
    "DAILYNEWS_BW",
    "PARLIAMENT_BW",
    "MINISTRY_BW",
    "REUTERS",
    "MMEGI",
    "SUNDAY_STANDARD",
    "BOTSWANA_GAZETTE",
    "WEEKEND_POST",
)

TARGET_FIELDS = (
    "after_stability_target_id",
    "linked_before_claim_id",
    "claim_family",
    "canonical_subject",
    "canonical_predicate",
    "canonical_object",
    "target_theme",
    "target_evidence_type",
    "preferred_source_family",
    "search_query",
    "reasoning_summary",
    "manual_review_required",
    "target_root",
)
TEMPLATE_FIELDS = (
    "after_candidate_id",
    "after_stability_target_id",
    "linked_before_claim_id",
    "target_theme",
    "target_evidence_type",
    "preferred_source_family",
    "url",
    "title",
    "publisher",
    "published_date",
    "verification_notes",
    "manual_review_required",
)
VALIDATED_CANDIDATE_FIELDS = (
    *TEMPLATE_FIELDS,
    "http_status",
    "content_type",
    "verification_status",
    "metadata_hash",
    "candidate_root",
)
REFUSAL_FIELDS = (
    "refusal_id",
    "after_candidate_id",
    "after_stability_target_id",
    "linked_before_claim_id",
    "target_theme",
    "target_evidence_type",
    "preferred_source_family",
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
    "REFUSED_UNSPECIFIED_URL",
    "REFUSED_MALFORMED_INTAKE_RECORD",
    "REFUSED_DUPLICATE_AFTER_CANDIDATE_ID",
    "REFUSED_DUPLICATE_AFTER_STABILITY_TARGET_ID",
    "REFUSED_UNKNOWN_AFTER_STABILITY_TARGET_ID",
    "REFUSED_TARGET_LINKAGE_MISMATCH",
    "REFUSED_INVALID_URL",
    "REFUSED_SEARCH_RESULT_URL",
    "REFUSED_UNREACHABLE",
    "REFUSED_METADATA_UNVERIFIED",
    "REFUSED_INPUT_VALIDATION",
)


class AfterCandidateRefusal(ValueError):
    def __init__(
        self,
        code: str,
        reason: str,
        http_status: int = 0,
        content_type: str = "",
    ):
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
        raise AfterCandidateRefusal(
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


def _target_root_material(target: Dict[str, Any]) -> Dict[str, Any]:
    return {field: target[field] for field in TARGET_FIELDS if field != "target_root"}


def _validated_metadata_material(validated: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: validated[field]
        for field in VALIDATED_CANDIDATE_FIELDS
        if field not in ("metadata_hash", "candidate_root")
    }


def _validated_root_material(validated: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: validated[field]
        for field in VALIDATED_CANDIDATE_FIELDS
        if field != "candidate_root"
    }


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    return {field: refusal[field] for field in REFUSAL_FIELDS if field != "refusal_root"}


def _closed_flags(data: Dict[str, Any]) -> bool:
    return (
        data.get("production_ready") is False
        and data.get("approved_evidence") == 0
        and data.get("public_ready") is False
        and data.get("institutional_ready") is False
    )


def _schema_payload() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "after_source_candidate_intake_only": True,
        "modes": ["dry-run", "validate-intake"],
        "target_schema_version": TARGET_SCHEMA_VERSION,
        "target_fields": list(TARGET_FIELDS),
        "template_fields": list(TEMPLATE_FIELDS),
        "validated_candidate_fields": list(VALIDATED_CANDIDATE_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "verification_status": VERIFIED_STATUS,
        "guardrails": {
            "urls_invented": 0,
            "web_searches_performed": 0,
            "source_pack_modified": False,
            "claims_created": 0,
            "contradictions_created": 0,
            "proof_chains_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
        },
        "root_rules": {
            "metadata_hash": "sha256 over validated candidate excluding metadata_hash and candidate_root",
            "candidate_root": "sha256 over validated candidate excluding candidate_root",
            "refusal_root": "sha256 over refusal excluding refusal_root",
        },
    }


def validate_schema(schema: Dict[str, Any]) -> None:
    if schema.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("AFTER-source candidate intake schema_version changed unexpectedly.")
    if schema.get("template_fields") != list(TEMPLATE_FIELDS):
        raise ValueError("AFTER-source candidate template fields changed unexpectedly.")
    if schema.get("validated_candidate_fields") != list(VALIDATED_CANDIDATE_FIELDS):
        raise ValueError("AFTER-source candidate validated fields changed unexpectedly.")
    if schema.get("refusal_fields") != list(REFUSAL_FIELDS):
        raise ValueError("AFTER-source candidate refusal fields changed unexpectedly.")


def _load_targets(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    if not isinstance(payload, dict) or not payload:
        raise ValueError("temporal_after_source_stability_targets.json is missing.")
    if payload.get("schema_version") != TARGET_SCHEMA_VERSION:
        raise ValueError("AFTER stability target schema_version is unsupported.")
    targets = payload.get("temporal_after_source_stability_targets")
    if not isinstance(targets, list):
        raise ValueError("temporal_after_source_stability_targets must be a list.")
    return targets


def validate_target(target: Dict[str, Any]) -> None:
    if not isinstance(target, dict) or set(target.keys()) != set(TARGET_FIELDS):
        raise ValueError("AFTER stability target fields changed unexpectedly.")
    for field_name in TARGET_FIELDS:
        if field_name == "manual_review_required":
            continue
        value = target.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"AFTER stability target {field_name} must be a non-empty string.")
    if target["target_theme"] not in TARGET_THEMES:
        raise ValueError("AFTER stability target target_theme unsupported.")
    if target["target_evidence_type"] not in TARGET_EVIDENCE_TYPES:
        raise ValueError("AFTER stability target target_evidence_type unsupported.")
    if target["preferred_source_family"] not in PREFERRED_SOURCE_FAMILIES:
        raise ValueError("AFTER stability target preferred_source_family unsupported.")
    if target["manual_review_required"] is not True:
        raise ValueError("AFTER stability target manual_review_required must remain true.")
    if target["target_root"] != _hash_json(_target_root_material(target)):
        raise ValueError(f"target_root mismatch for {target['after_stability_target_id']}.")


def _target_lookup(targets: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for target in targets:
        validate_target(target)
        target_id = target["after_stability_target_id"]
        if target_id in lookup:
            raise ValueError(f"Duplicate after_stability_target_id: {target_id}.")
        lookup[target_id] = target
    return lookup


def _load_template(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    if not isinstance(payload, dict) or not payload:
        raise ValueError("after_source_candidate_intake_template.json is missing.")
    if payload.get("production_ready") is not False:
        raise ValueError("AFTER-source candidate intake template production_ready must remain false.")
    if payload.get("manual_review_required") is not True:
        raise ValueError("AFTER-source candidate intake template manual_review_required must remain true.")
    intake = payload.get("after_source_candidate_intake")
    if not isinstance(intake, list):
        raise ValueError("AFTER-source candidate intake template must contain a list.")
    return intake


def _validate_record_shape(record: Dict[str, Any]) -> None:
    if not isinstance(record, dict):
        raise AfterCandidateRefusal(
            "REFUSED_MALFORMED_INTAKE_RECORD",
            "AFTER-source candidate intake record must be a JSON object.",
        )
    if set(record.keys()) != set(TEMPLATE_FIELDS):
        raise AfterCandidateRefusal(
            "REFUSED_MALFORMED_INTAKE_RECORD",
            "AFTER-source candidate intake record fields do not match schema.",
        )
    for field_name in TEMPLATE_FIELDS:
        if field_name == "manual_review_required":
            continue
        _require_nonempty_string(record, field_name, "AfterSourceCandidate")
    if record["target_theme"] not in TARGET_THEMES:
        raise AfterCandidateRefusal(
            "REFUSED_INPUT_VALIDATION",
            f"Unsupported target_theme: {record['target_theme']}.",
        )
    if record["target_evidence_type"] not in TARGET_EVIDENCE_TYPES:
        raise AfterCandidateRefusal(
            "REFUSED_INPUT_VALIDATION",
            f"Unsupported target_evidence_type: {record['target_evidence_type']}.",
        )
    if record["preferred_source_family"] not in PREFERRED_SOURCE_FAMILIES:
        raise AfterCandidateRefusal(
            "REFUSED_INPUT_VALIDATION",
            f"Unsupported preferred_source_family: {record['preferred_source_family']}.",
        )
    if record["manual_review_required"] is not True:
        raise AfterCandidateRefusal(
            "REFUSED_INPUT_VALIDATION",
            "AFTER-source candidate must require manual review.",
        )


def _validate_target_linkage(
    record: Dict[str, Any],
    target_by_id: Dict[str, Dict[str, Any]],
) -> None:
    target_id = record["after_stability_target_id"]
    target = target_by_id.get(target_id)
    if target is None:
        raise AfterCandidateRefusal(
            "REFUSED_UNKNOWN_AFTER_STABILITY_TARGET_ID",
            f"Unknown after_stability_target_id: {target_id}.",
        )
    for field_name in (
        "linked_before_claim_id",
        "target_theme",
        "target_evidence_type",
        "preferred_source_family",
    ):
        if record[field_name] != target[field_name]:
            raise AfterCandidateRefusal(
                "REFUSED_TARGET_LINKAGE_MISMATCH",
                f"{field_name} does not match target {target_id}.",
            )


def _validate_template_records(
    records: List[Dict[str, Any]],
    target_by_id: Dict[str, Dict[str, Any]],
) -> None:
    seen_candidate_ids = set()
    seen_target_ids = set()
    for record in records:
        _validate_record_shape(record)
        candidate_id = record["after_candidate_id"]
        if candidate_id in seen_candidate_ids:
            raise AfterCandidateRefusal(
                "REFUSED_DUPLICATE_AFTER_CANDIDATE_ID",
                f"Duplicate after_candidate_id: {candidate_id}.",
            )
        seen_candidate_ids.add(candidate_id)
        target_id = record["after_stability_target_id"]
        if target_id in seen_target_ids:
            raise AfterCandidateRefusal(
                "REFUSED_DUPLICATE_AFTER_STABILITY_TARGET_ID",
                f"Duplicate after_stability_target_id in template: {target_id}.",
            )
        seen_target_ids.add(target_id)
        _validate_target_linkage(record, target_by_id)


def _check_url_metadata(url: str, timeout: int = 15) -> Tuple[int, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; DumaBokoContradictionEngine/2.0; "
            "+https://example.invalid/manual-review)"
        )
    }
    last_error = ""
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = int(getattr(response, "status", response.getcode()) or 0)
                content_type = str(response.headers.get("Content-Type") or "").strip()
                if method == "GET":
                    response.read(1024)
                if 200 <= status <= 399 and content_type:
                    return status, content_type
                raise AfterCandidateRefusal(
                    "REFUSED_METADATA_UNVERIFIED",
                    "URL metadata was incomplete.",
                    http_status=status,
                    content_type=content_type,
                )
        except urllib.error.HTTPError as exc:
            status = int(exc.code or 0)
            content_type = str(exc.headers.get("Content-Type") or "").strip()
            last_error = f"HTTP {status}"
            if method == "HEAD" and status in (403, 405, 429, 500, 501, 502, 503):
                continue
            raise AfterCandidateRefusal(
                "REFUSED_UNREACHABLE",
                f"Candidate URL returned HTTP status {status}.",
                http_status=status,
                content_type=content_type,
            )
        except (urllib.error.URLError, TimeoutError, http.client.HTTPException) as exc:
            last_error = str(exc)
            if method == "HEAD":
                continue
    raise AfterCandidateRefusal(
        "REFUSED_UNREACHABLE",
        f"Candidate URL was unreachable: {last_error}",
    )


def _validate_supplied_candidate(record: Dict[str, Any]) -> Tuple[int, str]:
    url = record["url"].strip()
    if url == UNSPECIFIED:
        raise AfterCandidateRefusal(
            "REFUSED_UNSPECIFIED_URL",
            "AFTER-source candidate URL is UNSPECIFIED.",
        )
    if not _is_public_url(url):
        raise AfterCandidateRefusal(
            "REFUSED_INVALID_URL",
            "AFTER-source candidate URL must be public HTTP(S).",
        )
    if _is_generic_search_url(url):
        raise AfterCandidateRefusal(
            "REFUSED_SEARCH_RESULT_URL",
            "Search-result URLs cannot be accepted as AFTER-source candidates.",
        )
    for field_name in ("title", "publisher", "published_date", "verification_notes"):
        value = record[field_name].strip()
        if not value or value == UNSPECIFIED:
            raise AfterCandidateRefusal(
                "REFUSED_METADATA_UNVERIFIED",
                f"{field_name} must be supplied before URL validation.",
            )
    return _check_url_metadata(url)


def _validated_candidate(record: Dict[str, Any], http_status: int, content_type: str) -> Dict[str, Any]:
    validated = {
        **record,
        "http_status": http_status,
        "content_type": content_type,
        "verification_status": VERIFIED_STATUS,
        "metadata_hash": "",
        "candidate_root": "",
    }
    validated["metadata_hash"] = _hash_json(_validated_metadata_material(validated))
    validated["candidate_root"] = _hash_json(_validated_root_material(validated))
    return validated


def validate_validated_candidate(candidate: Dict[str, Any]) -> None:
    if set(candidate.keys()) != set(VALIDATED_CANDIDATE_FIELDS):
        raise ValueError("Validated AFTER-source candidate fields changed unexpectedly.")
    if candidate["verification_status"] != VERIFIED_STATUS:
        raise ValueError("Validated AFTER-source candidate verification_status changed unexpectedly.")
    if candidate["manual_review_required"] is not True:
        raise ValueError("Validated AFTER-source candidate manual_review_required must remain true.")
    if not isinstance(candidate["http_status"], int) or not (200 <= candidate["http_status"] <= 399):
        raise ValueError("Validated AFTER-source candidate http_status must be 200-399.")
    if not isinstance(candidate["content_type"], str) or not candidate["content_type"].strip():
        raise ValueError("Validated AFTER-source candidate content_type must be non-empty.")
    if candidate["metadata_hash"] != _hash_json(_validated_metadata_material(candidate)):
        raise ValueError(f"metadata_hash mismatch for {candidate['after_candidate_id']}.")
    if candidate["candidate_root"] != _hash_json(_validated_root_material(candidate)):
        raise ValueError(f"candidate_root mismatch for {candidate['after_candidate_id']}.")


def _make_refusal(record: Dict[str, Any], error: AfterCandidateRefusal, fallback_index: int) -> Dict[str, Any]:
    candidate_id = str(record.get("after_candidate_id") or f"UNKNOWN_{fallback_index:06d}")
    refusal = {
        "refusal_id": f"AFTER_SOURCE_CANDIDATE_INTAKE_REFUSAL_{candidate_id}",
        "after_candidate_id": str(record.get("after_candidate_id") or ""),
        "after_stability_target_id": str(record.get("after_stability_target_id") or ""),
        "linked_before_claim_id": str(record.get("linked_before_claim_id") or ""),
        "target_theme": str(record.get("target_theme") or ""),
        "target_evidence_type": str(record.get("target_evidence_type") or ""),
        "preferred_source_family": str(record.get("preferred_source_family") or ""),
        "url": str(record.get("url") or ""),
        "refusal_code": error.code,
        "refusal_reason": error.reason,
        "manual_review_required": True,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("AFTER-source candidate refusal fields changed unexpectedly.")
    for field_name in ("refusal_id", "refusal_code", "refusal_reason", "refusal_root"):
        value = refusal.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"AFTER-source candidate refusal {field_name} must be non-empty.")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("AFTER-source candidate refusal manual_review_required must remain true.")
    if not _closed_flags(refusal):
        raise ValueError("AFTER-source candidate refusal guardrails must remain closed.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}.")


def _build_validated_candidates(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    validated_candidates: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        try:
            http_status, content_type = _validate_supplied_candidate(record)
            candidate = _validated_candidate(record, http_status, content_type)
            validate_validated_candidate(candidate)
            validated_candidates.append(candidate)
        except AfterCandidateRefusal as error:
            refusal = _make_refusal(record if isinstance(record, dict) else {}, error, index)
            validate_refusal(refusal)
            refusals.append(refusal)
    return validated_candidates, refusals


def _status_for(mode: str, validated_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if validated_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if validated_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _build_report(
    status: str,
    mode: str,
    target_count: int,
    template_count: int,
    validated: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
) -> str:
    validated_lines = ["- None"]
    if validated:
        validated_lines = []
        for candidate in validated[:20]:
            validated_lines.extend(
                [
                    f"- {candidate['after_candidate_id']}: {candidate['url']}",
                    f"  - Target: {candidate['after_stability_target_id']}",
                    f"  - Source Family: {candidate['preferred_source_family']}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Candidate: {refusal['after_candidate_id']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# AFTER-Source Candidate Intake v2",
            "",
            "This lane validates human-supplied AFTER-source candidate URLs "
            "against stability targets. It does not invent URLs, search the "
            "web, modify the source pack, create claims, create contradictions, "
            "create proof chains, mark production readiness, or approve evidence.",
            "",
            "## Summary",
            f"- after_source_candidate_intake_status: {status}",
            f"- mode: {mode}",
            f"- after_target_count: {target_count}",
            f"- template_candidate_count: {template_count}",
            f"- validated_after_candidate_count: {len(validated)}",
            f"- refusal_count: {len(refusals)}",
            "",
            "## Validated AFTER Candidates",
            *validated_lines,
            "",
            "## Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- URLs Invented: 0",
            "- Web Searches Performed: 0",
            "- Source Pack Modified: False",
            "- Claims Created: 0",
            "- Contradictions Created: 0",
            "- Proof Chains Created: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "",
        ]
    )


def build_after_source_candidate_intake(
    mode: str = "dry-run",
    targets_path: Path = DEFAULT_TARGETS,
    template_path: Path = DEFAULT_TEMPLATE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "validate-intake"):
        raise ValueError("mode must be 'dry-run' or 'validate-intake'.")

    targets = _load_targets(targets_path)
    target_by_id = _target_lookup(targets)
    template_records = _load_template(template_path)
    _validate_template_records(template_records, target_by_id)
    schema = _schema_payload()
    validate_schema(schema)

    validated_candidates: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    if mode == "validate-intake":
        validated_candidates, refusals = _build_validated_candidates(template_records)

    status = _status_for(mode, len(validated_candidates), len(refusals))
    report = _build_report(
        status,
        mode,
        len(targets),
        len(template_records),
        validated_candidates,
        refusals,
    )
    summary = {
        "after_source_candidate_intake_status": status,
        "mode": mode,
        "after_target_count": len(targets),
        "template_candidate_count": len(template_records),
        "validated_after_candidate_count": len(validated_candidates),
        "refusal_count": len(refusals),
        "validated_candidate_roots": [
            candidate["candidate_root"] for candidate in validated_candidates
        ],
        "refusal_roots": [refusal["refusal_root"] for refusal in refusals],
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "after_source_candidate_intake_schema_hash": _hash_json(schema),
        "after_source_candidate_intake_report_hash": _sha256_text(report),
        "urls_invented": 0,
        "web_searches_performed": 0,
        "source_pack_modified": False,
        "claims_created": 0,
        "contradictions_created": 0,
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
    for counter_name in (
        "urls_invented",
        "web_searches_performed",
        "claims_created",
        "contradictions_created",
        "proof_chains_created",
        "final_reports_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0.")
    if summary["source_pack_modified"] is not False:
        raise ValueError("Source pack must not be modified by AFTER-source candidate intake.")
    if not _closed_flags(summary):
        raise ValueError("AFTER-source candidate intake guardrails must remain closed.")

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(
        output_dir / VALIDATED_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "validated_after_source_candidates": validated_candidates,
        },
    )
    _write_json(
        output_dir / REFUSALS_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "after_source_candidate_intake_refusals": refusals,
        },
    )
    _write_json(output_dir / SCHEMA_OUTPUT.name, schema)
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    return {
        "summary": summary,
        "validated_after_source_candidates": validated_candidates,
        "after_source_candidate_intake_refusals": refusals,
        "schema": schema,
        "report": report,
    }


__all__ = ["build_after_source_candidate_intake"]
