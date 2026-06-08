#!/usr/bin/env python3
"""
Manual AFTER Source Snapshot Intake v2.

Validates human-supplied AFTER source snapshots for temporal sources that cannot
be live-harvested. This lane does not fetch URLs, search the web, modify the
source pack, create claims, create contradictions, run graph/adjudication logic,
create proof chains, create final reports, mark production readiness, or approve
evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple
import hashlib
import json


DEFAULT_TEMPLATE = Path(
    "inputs/temporal_sources/manual_after_source_snapshot_template.json"
)
DEFAULT_AFTER_CANDIDATES = Path(
    "inputs/temporal_sources/after_source_candidate_intake_template.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/manual_after_source_snapshot_intake")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_after_source_snapshot_intake_summary.json"
VALIDATED_OUTPUT = DEFAULT_OUTPUT_DIR / "validated_manual_after_snapshots.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_after_source_snapshot_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_after_source_snapshot_intake_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_after_source_snapshot_intake_schema.json"

SCHEMA_VERSION = "manual_after_source_snapshot_intake_v2"
AFTER_CANDIDATE_TEMPLATE_VERSION = "after_source_candidate_intake_template_v2"

DRY_RUN_STATUS = "MANUAL_AFTER_SOURCE_SNAPSHOT_INTAKE_DRY_RUN_VALIDATED"
VALIDATED_STATUS = "MANUAL_AFTER_SOURCE_SNAPSHOT_INTAKE_VALIDATED"
PARTIAL_STATUS = "MANUAL_AFTER_SOURCE_SNAPSHOT_INTAKE_PARTIAL"
REFUSED_STATUS = "MANUAL_AFTER_SOURCE_SNAPSHOT_INTAKE_REFUSED"

VALIDATION_STATUS = "VALIDATED_MANUAL_AFTER_SOURCE_SNAPSHOT"
UNSPECIFIED = "UNSPECIFIED"

SNAPSHOT_FIELDS = (
    "snapshot_id",
    "linked_after_candidate_id",
    "url",
    "title",
    "publisher",
    "published_date",
    "snapshot_text",
    "verification_notes",
    "manual_review_required",
)
AFTER_CANDIDATE_FIELDS = (
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
VALIDATED_SNAPSHOT_FIELDS = (
    *SNAPSHOT_FIELDS,
    "after_stability_target_id",
    "linked_before_claim_id",
    "target_theme",
    "target_evidence_type",
    "preferred_source_family",
    "validation_status",
    "linked_after_candidate_record_hash",
    "snapshot_text_hash",
    "metadata_hash",
    "snapshot_root",
)
REFUSAL_FIELDS = (
    "refusal_id",
    "snapshot_id",
    "linked_after_candidate_id",
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
    "REFUSED_UNKNOWN_AFTER_CANDIDATE",
    "REFUSED_METADATA_MISMATCH",
    "REFUSED_MALFORMED_SNAPSHOT_RECORD",
    "REFUSED_DUPLICATE_SNAPSHOT_ID",
    "REFUSED_DUPLICATE_LINKED_AFTER_CANDIDATE",
    "REFUSED_INPUT_VALIDATION",
)
METADATA_MATCH_FIELDS = (
    "url",
    "title",
    "publisher",
    "published_date",
    "verification_notes",
)


class ManualAfterSnapshotRefusal(ValueError):
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


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ManualAfterSnapshotRefusal(
            "REFUSED_MALFORMED_SNAPSHOT_RECORD",
            f"{object_name}.{field_name} must be a non-empty string.",
        )


def _schema_payload() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "manual_after_source_snapshot_intake_only": True,
        "modes": ["dry-run", "validate"],
        "after_candidate_template_version": AFTER_CANDIDATE_TEMPLATE_VERSION,
        "snapshot_fields": list(SNAPSHOT_FIELDS),
        "after_candidate_fields": list(AFTER_CANDIDATE_FIELDS),
        "validated_snapshot_fields": list(VALIDATED_SNAPSHOT_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "validation_status": VALIDATION_STATUS,
        "guardrails": {
            "urls_invented": 0,
            "web_searches_performed": 0,
            "urls_fetched": 0,
            "source_pack_modified": False,
            "claims_created": 0,
            "contradictions_created": 0,
            "graph_logic_modified": False,
            "adjudication_logic_modified": False,
            "proof_chains_created": 0,
            "final_reports_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
        },
        "root_rules": {
            "linked_after_candidate_record_hash": "sha256 over linked AFTER candidate template record",
            "snapshot_text_hash": "sha256 over snapshot_text",
            "metadata_hash": (
                "sha256 over validated manual AFTER snapshot excluding metadata_hash and snapshot_root"
            ),
            "snapshot_root": "sha256 over validated manual AFTER snapshot excluding snapshot_root",
            "refusal_root": "sha256 over refusal excluding refusal_root",
        },
    }


def validate_schema(schema: Dict[str, Any]) -> None:
    if schema.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Manual AFTER snapshot intake schema_version changed unexpectedly.")
    if schema.get("snapshot_fields") != list(SNAPSHOT_FIELDS):
        raise ValueError("Manual AFTER snapshot fields changed unexpectedly.")
    if schema.get("validated_snapshot_fields") != list(VALIDATED_SNAPSHOT_FIELDS):
        raise ValueError("Manual AFTER validated snapshot fields changed unexpectedly.")
    if schema.get("refusal_fields") != list(REFUSAL_FIELDS):
        raise ValueError("Manual AFTER snapshot refusal fields changed unexpectedly.")


def _load_after_candidates(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    if not isinstance(payload, dict) or not payload:
        raise ValueError("after_source_candidate_intake_template.json is missing.")
    if payload.get("template_version") != AFTER_CANDIDATE_TEMPLATE_VERSION:
        raise ValueError("AFTER-source candidate template version is unsupported.")
    if payload.get("production_ready") is not False:
        raise ValueError("AFTER-source candidate template production_ready must remain false.")
    if payload.get("manual_review_required") is not True:
        raise ValueError("AFTER-source candidate template manual_review_required must remain true.")
    candidates = payload.get("after_source_candidate_intake")
    if not isinstance(candidates, list):
        raise ValueError("AFTER-source candidate template must contain a list.")
    return candidates


def _validate_after_candidate(candidate: Dict[str, Any]) -> None:
    if not isinstance(candidate, dict) or set(candidate.keys()) != set(AFTER_CANDIDATE_FIELDS):
        raise ValueError("AFTER-source candidate fields changed unexpectedly.")
    for field_name in AFTER_CANDIDATE_FIELDS:
        if field_name == "manual_review_required":
            continue
        value = candidate.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"AFTER-source candidate {field_name} must be a non-empty string.")
    if candidate["manual_review_required"] is not True:
        raise ValueError("AFTER-source candidate manual_review_required must remain true.")


def _after_candidate_lookup(candidates: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for candidate in candidates:
        _validate_after_candidate(candidate)
        candidate_id = candidate["after_candidate_id"]
        if candidate_id in lookup:
            raise ValueError(f"Duplicate after_candidate_id: {candidate_id}.")
        lookup[candidate_id] = candidate
    return lookup


def _load_snapshot_template(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    if not isinstance(payload, dict) or not payload:
        raise ValueError("manual_after_source_snapshot_template.json is missing.")
    if payload.get("production_ready") is not False:
        raise ValueError("Manual AFTER snapshot template production_ready must remain false.")
    if payload.get("manual_review_required") is not True:
        raise ValueError("Manual AFTER snapshot template manual_review_required must remain true.")
    snapshots = payload.get("manual_after_source_snapshots")
    if not isinstance(snapshots, list):
        raise ValueError("Manual AFTER snapshot template must contain a list.")
    return snapshots


def _validate_snapshot_shape(snapshot: Dict[str, Any]) -> None:
    if not isinstance(snapshot, dict):
        raise ManualAfterSnapshotRefusal(
            "REFUSED_MALFORMED_SNAPSHOT_RECORD",
            "Manual AFTER snapshot record must be a JSON object.",
        )
    if set(snapshot.keys()) != set(SNAPSHOT_FIELDS):
        raise ManualAfterSnapshotRefusal(
            "REFUSED_MALFORMED_SNAPSHOT_RECORD",
            "Manual AFTER snapshot record fields do not match schema.",
        )
    for field_name in SNAPSHOT_FIELDS:
        if field_name == "manual_review_required":
            continue
        _require_nonempty_string(snapshot, field_name, "ManualAfterSourceSnapshot")
    if snapshot["manual_review_required"] is not True:
        raise ManualAfterSnapshotRefusal(
            "REFUSED_INPUT_VALIDATION",
            "Manual AFTER snapshot must require manual review.",
        )


def _validate_metadata_match(
    snapshot: Dict[str, Any],
    after_candidate_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    candidate_id = snapshot["linked_after_candidate_id"]
    candidate = after_candidate_by_id.get(candidate_id)
    if candidate is None:
        raise ManualAfterSnapshotRefusal(
            "REFUSED_UNKNOWN_AFTER_CANDIDATE",
            f"Unknown linked_after_candidate_id: {candidate_id}.",
        )
    if candidate["url"] == UNSPECIFIED:
        raise ManualAfterSnapshotRefusal(
            "REFUSED_UNKNOWN_AFTER_CANDIDATE",
            f"Linked AFTER candidate {candidate_id} has UNSPECIFIED URL.",
        )
    for field_name in METADATA_MATCH_FIELDS:
        if snapshot[field_name] != candidate[field_name]:
            raise ManualAfterSnapshotRefusal(
                "REFUSED_METADATA_MISMATCH",
                f"{field_name} does not match linked AFTER candidate {candidate_id}.",
            )
    return candidate


def _validate_snapshot_records(
    snapshots: List[Dict[str, Any]],
    after_candidate_by_id: Dict[str, Dict[str, Any]],
) -> None:
    seen_snapshot_ids = set()
    seen_candidate_ids = set()
    for index, snapshot in enumerate(snapshots, start=1):
        try:
            _validate_snapshot_shape(snapshot)
            snapshot_id = snapshot["snapshot_id"]
            if snapshot_id in seen_snapshot_ids:
                raise ManualAfterSnapshotRefusal(
                    "REFUSED_DUPLICATE_SNAPSHOT_ID",
                    f"Duplicate snapshot_id: {snapshot_id}.",
                )
            seen_snapshot_ids.add(snapshot_id)
            candidate_id = snapshot["linked_after_candidate_id"]
            if candidate_id in seen_candidate_ids:
                raise ManualAfterSnapshotRefusal(
                    "REFUSED_DUPLICATE_LINKED_AFTER_CANDIDATE",
                    f"Duplicate linked_after_candidate_id: {candidate_id}.",
                )
            seen_candidate_ids.add(candidate_id)
            _validate_metadata_match(snapshot, after_candidate_by_id)
        except ManualAfterSnapshotRefusal as error:
            raise ValueError(f"Snapshot template shape validation failed at row {index}: {error.reason}") from error


def _candidate_record_hash(candidate: Dict[str, Any]) -> str:
    return _hash_json({field: candidate[field] for field in AFTER_CANDIDATE_FIELDS})


def _validated_metadata_material(validated: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: validated[field]
        for field in VALIDATED_SNAPSHOT_FIELDS
        if field not in ("metadata_hash", "snapshot_root")
    }


def _validated_root_material(validated: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: validated[field]
        for field in VALIDATED_SNAPSHOT_FIELDS
        if field != "snapshot_root"
    }


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    return {field: refusal[field] for field in REFUSAL_FIELDS if field != "refusal_root"}


def _validate_supplied_snapshot(snapshot: Dict[str, Any]) -> None:
    snapshot_text = snapshot["snapshot_text"].strip()
    if not snapshot_text or snapshot_text == UNSPECIFIED:
        raise ManualAfterSnapshotRefusal(
            "REFUSED_EMPTY_SNAPSHOT",
            "snapshot_text must be supplied before manual AFTER snapshot validation.",
        )


def _validated_snapshot(snapshot: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    validated = {
        **snapshot,
        "after_stability_target_id": candidate["after_stability_target_id"],
        "linked_before_claim_id": candidate["linked_before_claim_id"],
        "target_theme": candidate["target_theme"],
        "target_evidence_type": candidate["target_evidence_type"],
        "preferred_source_family": candidate["preferred_source_family"],
        "validation_status": VALIDATION_STATUS,
        "linked_after_candidate_record_hash": _candidate_record_hash(candidate),
        "snapshot_text_hash": _sha256_text(snapshot["snapshot_text"]),
        "metadata_hash": "",
        "snapshot_root": "",
    }
    validated["metadata_hash"] = _hash_json(_validated_metadata_material(validated))
    validated["snapshot_root"] = _hash_json(_validated_root_material(validated))
    return validated


def validate_validated_snapshot(snapshot: Dict[str, Any]) -> None:
    if set(snapshot.keys()) != set(VALIDATED_SNAPSHOT_FIELDS):
        raise ValueError("Validated manual AFTER snapshot fields changed unexpectedly.")
    if snapshot["validation_status"] != VALIDATION_STATUS:
        raise ValueError("Validated manual AFTER snapshot validation_status changed unexpectedly.")
    if snapshot["manual_review_required"] is not True:
        raise ValueError("Validated manual AFTER snapshot manual_review_required must remain true.")
    if not isinstance(snapshot["snapshot_text"], str) or snapshot["snapshot_text"].strip() == UNSPECIFIED:
        raise ValueError("Validated manual AFTER snapshot snapshot_text must be supplied.")
    if snapshot["snapshot_text_hash"] != _sha256_text(snapshot["snapshot_text"]):
        raise ValueError(f"snapshot_text_hash mismatch for {snapshot['snapshot_id']}.")
    if snapshot["metadata_hash"] != _hash_json(_validated_metadata_material(snapshot)):
        raise ValueError(f"metadata_hash mismatch for {snapshot['snapshot_id']}.")
    if snapshot["snapshot_root"] != _hash_json(_validated_root_material(snapshot)):
        raise ValueError(f"snapshot_root mismatch for {snapshot['snapshot_id']}.")


def _make_refusal(snapshot: Dict[str, Any], error: ManualAfterSnapshotRefusal, index: int) -> Dict[str, Any]:
    snapshot_id = str(snapshot.get("snapshot_id") or f"UNKNOWN_{index:06d}")
    refusal = {
        "refusal_id": f"MANUAL_AFTER_SOURCE_SNAPSHOT_REFUSAL_{snapshot_id}",
        "snapshot_id": str(snapshot.get("snapshot_id") or ""),
        "linked_after_candidate_id": str(snapshot.get("linked_after_candidate_id") or ""),
        "url": str(snapshot.get("url") or ""),
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
        raise ValueError("Manual AFTER snapshot refusal fields changed unexpectedly.")
    for field_name in ("refusal_id", "refusal_code", "refusal_reason", "refusal_root"):
        value = refusal.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Manual AFTER snapshot refusal {field_name} must be non-empty.")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("Manual AFTER snapshot refusal manual_review_required must remain true.")
    if not _closed_flags(refusal):
        raise ValueError("Manual AFTER snapshot refusal guardrails must remain closed.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}.")


def _build_validated_snapshots(
    snapshots: List[Dict[str, Any]],
    after_candidate_by_id: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    validated_snapshots: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    seen_snapshot_ids = set()
    seen_candidate_ids = set()
    for index, snapshot in enumerate(snapshots, start=1):
        try:
            _validate_snapshot_shape(snapshot)
            snapshot_id = snapshot["snapshot_id"]
            if snapshot_id in seen_snapshot_ids:
                raise ManualAfterSnapshotRefusal(
                    "REFUSED_DUPLICATE_SNAPSHOT_ID",
                    f"Duplicate snapshot_id: {snapshot_id}.",
                )
            seen_snapshot_ids.add(snapshot_id)
            candidate_id = snapshot["linked_after_candidate_id"]
            if candidate_id in seen_candidate_ids:
                raise ManualAfterSnapshotRefusal(
                    "REFUSED_DUPLICATE_LINKED_AFTER_CANDIDATE",
                    f"Duplicate linked_after_candidate_id: {candidate_id}.",
                )
            seen_candidate_ids.add(candidate_id)
            candidate = _validate_metadata_match(snapshot, after_candidate_by_id)
            _validate_supplied_snapshot(snapshot)
            validated = _validated_snapshot(snapshot, candidate)
            validate_validated_snapshot(validated)
            validated_snapshots.append(validated)
        except ManualAfterSnapshotRefusal as error:
            refusal = _make_refusal(snapshot if isinstance(snapshot, dict) else {}, error, index)
            validate_refusal(refusal)
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


def _summary_root_material(summary: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {
        "manual_after_source_snapshot_intake_root",
        "manual_after_source_snapshot_intake_report_hash",
    }
    return {key: value for key, value in summary.items() if key not in excluded}


def _build_report(
    status: str,
    mode: str,
    snapshot_count: int,
    validated: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    validated_lines = ["- None"]
    if validated:
        validated_lines = []
        for snapshot in validated[:20]:
            validated_lines.extend(
                [
                    f"- {snapshot['snapshot_id']}: {snapshot['url']}",
                    f"  - Linked AFTER Candidate: {snapshot['linked_after_candidate_id']}",
                    f"  - Status: {snapshot['validation_status']}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Snapshot: {refusal['snapshot_id']}",
                    f"  - Candidate: {refusal['linked_after_candidate_id']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Manual AFTER Source Snapshot Intake v2",
            "",
            "This lane validates human-supplied AFTER source snapshots when live "
            "harvesting fails. It does not search the web, fetch URLs, modify the "
            "source pack, create claims, create contradictions, run graph or "
            "adjudication logic, create proof chains, create final reports, mark "
            "production readiness, or approve evidence.",
            "",
            "## Summary",
            f"- manual_after_source_snapshot_intake_status: {status}",
            f"- mode: {mode}",
            f"- snapshot_template_count: {snapshot_count}",
            f"- validated_snapshot_count: {len(validated)}",
            f"- refusal_count: {len(refusals)}",
            f"- manual_after_source_snapshot_intake_root: {root}",
            "",
            "## Validated Manual AFTER Snapshots",
            *validated_lines,
            "",
            "## Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- URLs Invented: 0",
            "- Web Searches Performed: 0",
            "- URLs Fetched: 0",
            "- Source Pack Modified: False",
            "- Claims Created: 0",
            "- Contradictions Created: 0",
            "- Graph Logic Modified: False",
            "- Adjudication Logic Modified: False",
            "- Proof Chains Created: 0",
            "- Final Reports Created: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "",
        ]
    )


def build_manual_after_source_snapshot_intake(
    mode: str = "dry-run",
    snapshot_template_path: Path = DEFAULT_TEMPLATE,
    after_candidates_path: Path = DEFAULT_AFTER_CANDIDATES,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "validate"):
        raise ValueError("mode must be 'dry-run' or 'validate'.")

    after_candidates = _load_after_candidates(after_candidates_path)
    after_candidate_by_id = _after_candidate_lookup(after_candidates)
    snapshots = _load_snapshot_template(snapshot_template_path)
    if mode == "dry-run":
        _validate_snapshot_records(snapshots, after_candidate_by_id)
    schema = _schema_payload()
    validate_schema(schema)

    validated_snapshots: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    if mode == "validate":
        validated_snapshots, refusals = _build_validated_snapshots(
            snapshots,
            after_candidate_by_id,
        )

    status = _status_for(mode, len(validated_snapshots), len(refusals))
    summary = {
        "manual_after_source_snapshot_intake_status": status,
        "mode": mode,
        "snapshot_template_count": len(snapshots),
        "validated_snapshot_count": len(validated_snapshots),
        "refusal_count": len(refusals),
        "validated_snapshot_ids": [
            snapshot["snapshot_id"] for snapshot in validated_snapshots
        ],
        "validated_snapshot_roots": [
            snapshot["snapshot_root"] for snapshot in validated_snapshots
        ],
        "refusal_roots": [refusal["refusal_root"] for refusal in refusals],
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "manual_after_source_snapshot_intake_schema_hash": _hash_json(schema),
        "manual_after_source_snapshot_intake_report_hash": "",
        "manual_after_source_snapshot_intake_root": "",
        "urls_invented": 0,
        "web_searches_performed": 0,
        "urls_fetched": 0,
        "source_pack_modified": False,
        "claims_created": 0,
        "contradictions_created": 0,
        "graph_logic_modified": False,
        "adjudication_logic_modified": False,
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
    summary["manual_after_source_snapshot_intake_root"] = _hash_json(
        _summary_root_material(summary)
    )
    report = _build_report(
        status,
        mode,
        len(snapshots),
        validated_snapshots,
        refusals,
        summary["manual_after_source_snapshot_intake_root"],
    )
    summary["manual_after_source_snapshot_intake_report_hash"] = _sha256_text(report)
    summary["manual_after_source_snapshot_intake_root"] = _hash_json(
        _summary_root_material(summary)
    )
    report = _build_report(
        status,
        mode,
        len(snapshots),
        validated_snapshots,
        refusals,
        summary["manual_after_source_snapshot_intake_root"],
    )

    for counter_name in (
        "urls_invented",
        "web_searches_performed",
        "urls_fetched",
        "claims_created",
        "contradictions_created",
        "proof_chains_created",
        "final_reports_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0.")
    for flag_name in (
        "source_pack_modified",
        "graph_logic_modified",
        "adjudication_logic_modified",
    ):
        if summary[flag_name] is not False:
            raise ValueError(f"{flag_name} must remain false.")
    if not _closed_flags(summary):
        raise ValueError("Manual AFTER snapshot intake guardrails must remain closed.")

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(
        output_dir / VALIDATED_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "validated_manual_after_snapshots": validated_snapshots,
        },
    )
    _write_json(
        output_dir / REFUSALS_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "manual_after_source_snapshot_refusals": refusals,
        },
    )
    _write_json(output_dir / SCHEMA_OUTPUT.name, schema)
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    return {
        "summary": summary,
        "validated_manual_after_snapshots": validated_snapshots,
        "manual_after_source_snapshot_refusals": refusals,
        "schema": schema,
        "report": report,
    }


__all__ = ["build_manual_after_source_snapshot_intake"]
