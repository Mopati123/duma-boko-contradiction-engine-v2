#!/usr/bin/env python3
"""
Complete safe evidence-location metadata without fabricating exact evidence.
"""

import argparse
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.evidence_location_model import (
    has_exact_value,
    missing_location_required_fields,
    validate_no_placeholder_final_evidence,
    validate_no_fake_timestamps_for_text_source,
)


DEFAULT_TEMPLATE_DIR = Path("data/real_evidence_inputs")
DEFAULT_OUTPUT_DIR = Path("outputs/exact_evidence_field_completion")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "exact_evidence_field_completion_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "exact_evidence_field_completion_summary.json"
MISSING_FIELDS_OUTPUT = DEFAULT_OUTPUT_DIR / "missing_exact_evidence_fields.json"

JOBS_EVIDENCE_ID = "VID_JOBS_001"
HEALTH_EVIDENCE_ID = "VID_HEALTH_001"
LOCATION_TYPES_BY_EVIDENCE_ID = {
    JOBS_EVIDENCE_ID: "document_reference",
    HEALTH_EVIDENCE_ID: "article_reference",
}

FORBIDDEN_FIELDS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

COMPLETION_STATUSES = {
    "blocked_missing_exact_fields",
    "would_update_location_metadata",
    "location_metadata_present",
}


@dataclass
class ExactEvidenceFieldCompletionRecord:
    evidence_id: str
    template_path: str
    completion_status: str
    original_evidence_location_type: str
    proposed_evidence_location_type: str
    changed_fields: List[str]
    missing_exact_fields: List[str]
    blocker_reasons: List[str]
    would_write_template: bool
    backup_path: str
    quote_text_filled: bool
    transcript_or_excerpt_filled: bool
    placeholders_treated_as_final_evidence: bool
    verified_for_approval_review: bool
    approved_evidence: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    proposed_template: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_template(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Template must be a JSON object: {path}")
    return data


def _selected_template_paths(
    evidence_id: str = "",
    template_dir: Path = DEFAULT_TEMPLATE_DIR,
) -> List[Path]:
    if evidence_id and evidence_id not in LOCATION_TYPES_BY_EVIDENCE_ID:
        raise ValueError(f"Unsupported evidence_id: {evidence_id}")
    if evidence_id:
        return [template_dir / f"{evidence_id}.template.json"]
    return [
        template_dir / f"{JOBS_EVIDENCE_ID}.template.json",
        template_dir / f"{HEALTH_EVIDENCE_ID}.template.json",
    ]


def _reject_forbidden_flags(data: Dict[str, Any]) -> None:
    for field_name in FORBIDDEN_FIELDS:
        if data.get(field_name) is True:
            raise ValueError(f"Exact evidence completion must not set {field_name}=true")
    if data.get("verified_for_approval_review") is True:
        raise ValueError(
            "Exact evidence completion must not contain "
            "verified_for_approval_review=true"
        )


def proposed_template_with_location(template: Dict[str, Any]) -> Dict[str, Any]:
    _reject_forbidden_flags(template)
    evidence_id = str(template.get("evidence_id", ""))
    if evidence_id not in LOCATION_TYPES_BY_EVIDENCE_ID:
        raise ValueError(f"Unsupported evidence_id: {evidence_id}")
    if not has_exact_value(template.get("source_url")):
        raise ValueError("source_url must be a non-empty string")

    proposed = dict(template)
    proposed["evidence_location_type"] = LOCATION_TYPES_BY_EVIDENCE_ID[evidence_id]
    validate_no_fake_timestamps_for_text_source(proposed)
    return proposed


def build_completion_record(
    template: Dict[str, Any],
    template_path: Path = Path(""),
) -> ExactEvidenceFieldCompletionRecord:
    proposed = proposed_template_with_location(template)
    evidence_id = str(proposed.get("evidence_id", ""))
    original_location_type = str(template.get("evidence_location_type", ""))
    proposed_location_type = str(proposed.get("evidence_location_type", ""))
    changed_fields = [
        field_name
        for field_name in ("evidence_location_type",)
        if template.get(field_name, "") != proposed.get(field_name, "")
    ]
    missing = missing_location_required_fields(proposed, require_location_type=True)
    blockers = []
    if missing:
        blockers.append("missing exact evidence fields: " + ", ".join(missing))
    completion_status = (
        "would_update_location_metadata"
        if changed_fields
        else "location_metadata_present"
    )
    if missing:
        completion_status = "blocked_missing_exact_fields"

    record = ExactEvidenceFieldCompletionRecord(
        evidence_id=evidence_id,
        template_path=str(template_path),
        completion_status=completion_status,
        original_evidence_location_type=original_location_type,
        proposed_evidence_location_type=proposed_location_type,
        changed_fields=changed_fields,
        missing_exact_fields=missing,
        blocker_reasons=blockers,
        would_write_template=False,
        backup_path="",
        quote_text_filled=False,
        transcript_or_excerpt_filled=False,
        placeholders_treated_as_final_evidence=False,
        verified_for_approval_review=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        proposed_template=proposed,
    )
    validate_completion_record(record)
    return record


def validate_completion_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record
    if not isinstance(data, dict):
        raise ValueError(f"Expected object or dict, got {type(data).__name__}")
    for field_name in (
        "evidence_id",
        "template_path",
        "completion_status",
        "proposed_evidence_location_type",
    ):
        value = data.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"ExactEvidenceFieldCompletionRecord.{field_name} required")
    if data.get("verified_for_approval_review") is not False:
        raise ValueError("Exact evidence completion must not approval-verify")
    if data["completion_status"] not in COMPLETION_STATUSES:
        raise ValueError(
            "ExactEvidenceFieldCompletionRecord.completion_status is unsupported: "
            f"{data['completion_status']}"
        )
    if data.get("approved_evidence") is not False:
        raise ValueError("Exact evidence completion must not approve evidence")
    for field_name in ("public_ready", "institutional_ready", "report_ready"):
        if data.get(field_name) is not False:
            raise ValueError(f"Exact evidence completion must not set {field_name}")
    proposed = data.get("proposed_template")
    if not isinstance(proposed, dict):
        raise ValueError("Exact evidence completion proposed_template required")
    if not proposed.get("evidence_location_type"):
        raise ValueError("evidence_location_type is missing after update")
    if not has_exact_value(proposed.get("source_url")):
        raise ValueError("source_url must be a non-empty string")
    validate_no_fake_timestamps_for_text_source(proposed)
    if not data.get("missing_exact_fields"):
        validate_no_placeholder_final_evidence(proposed)
    if set(data.get("changed_fields", [])) - {"evidence_location_type"}:
        raise ValueError("Exact evidence completion may only change location metadata")


def _write_template(path: Path, proposed: Dict[str, Any]) -> str:
    validate_no_fake_timestamps_for_text_source(proposed)
    backup_path = path.with_name(f"{path.name}.bak")
    shutil.copy2(path, backup_path)
    path.write_text(
        json.dumps(proposed, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return str(backup_path)


def summarize_records(
    records: List[ExactEvidenceFieldCompletionRecord],
    mode: str,
) -> Dict[str, Any]:
    return {
        "generated_at_utc": utc_now_iso(),
        "mode": mode,
        "selected_template_count": len(records),
        "location_metadata_present_count": sum(
            1 for record in records if record.proposed_evidence_location_type
        ),
        "blocked_missing_exact_fields_count": sum(
            1 for record in records if record.missing_exact_fields
        ),
        "write_count": sum(1 for record in records if record.backup_path),
        "backup_count": sum(1 for record in records if record.backup_path),
        "quote_text_filled_count": sum(1 for record in records if record.quote_text_filled),
        "transcript_or_excerpt_filled_count": sum(
            1 for record in records if record.transcript_or_excerpt_filled
        ),
        "placeholders_treated_as_final_evidence": False,
        "verified_for_approval_review": 0,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
        "evidence_ids": [record.evidence_id for record in records],
    }


def write_outputs(
    records: List[ExactEvidenceFieldCompletionRecord],
    mode: str,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, str]:
    for record in records:
        validate_completion_record(record)
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / STATUS_OUTPUT.name
    summary_path = output_dir / SUMMARY_OUTPUT.name
    missing_path = output_dir / MISSING_FIELDS_OUTPUT.name
    summary = summarize_records(records, mode)
    summary["status_output"] = str(status_path)
    summary["summary_output"] = str(summary_path)
    summary["missing_fields_output"] = str(missing_path)
    status_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "generated_at_utc": utc_now_iso(),
                    "mode": mode,
                    "approved_evidence": 0,
                    "public_ready": False,
                    "institutional_ready": False,
                    "report_ready": False,
                },
                "records": [record.to_dict() for record in records],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    missing_path.write_text(
        json.dumps(
            {
                record.evidence_id: record.missing_exact_fields
                for record in records
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "status_output": str(status_path),
        "summary_output": str(summary_path),
        "missing_fields_output": str(missing_path),
    }


def complete_exact_evidence_fields(
    evidence_id: str = "",
    write: bool = False,
    template_dir: Path = DEFAULT_TEMPLATE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    records: List[ExactEvidenceFieldCompletionRecord] = []
    for path in _selected_template_paths(evidence_id=evidence_id, template_dir=template_dir):
        template = _load_template(path)
        record = build_completion_record(template, path)
        if write and record.changed_fields:
            backup_path = _write_template(path, record.proposed_template)
            record.backup_path = backup_path
            record.would_write_template = True
            validate_completion_record(record)
        records.append(record)

    mode = "write" if write else "dry-run"
    outputs = write_outputs(records, mode=mode, output_dir=output_dir)
    summary = summarize_records(records, mode)
    summary.update(outputs)
    summary["records"] = records
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Complete safe exact-evidence location metadata."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Inspect without writing.")
    mode.add_argument(
        "--write",
        action="store_true",
        help="Write safe evidence_location_type metadata only.",
    )
    parser.add_argument(
        "--evidence-id",
        choices=(JOBS_EVIDENCE_ID, HEALTH_EVIDENCE_ID),
        help="Limit completion to one evidence ID.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = complete_exact_evidence_fields(
        evidence_id=args.evidence_id or "",
        write=args.write,
    )
    print("== Exact Evidence Field Completion v1 summary ==")
    print(f"Mode: {summary['mode']}")
    if args.evidence_id:
        print(f"evidence_id: {args.evidence_id}")
    print(f"selected_template_count: {summary['selected_template_count']}")
    print(
        "location_metadata_present_count: "
        f"{summary['location_metadata_present_count']}"
    )
    print(
        "blocked_missing_exact_fields_count: "
        f"{summary['blocked_missing_exact_fields_count']}"
    )
    print(f"write_count: {summary['write_count']}")
    print(f"backup_count: {summary['backup_count']}")
    print(f"quote_text_filled_count: {summary['quote_text_filled_count']}")
    print(
        "transcript_or_excerpt_filled_count: "
        f"{summary['transcript_or_excerpt_filled_count']}"
    )
    print(
        "placeholders_treated_as_final_evidence: "
        f"{summary['placeholders_treated_as_final_evidence']}"
    )
    print(
        "verified_for_approval_review: "
        f"{summary['verified_for_approval_review']}"
    )
    print(f"approved_evidence: {summary['approved_evidence']}")
    print(f"public_ready: {summary['public_ready']}")
    print(f"institutional_ready: {summary['institutional_ready']}")
    print(f"report_ready: {summary['report_ready']}")
    print(f"status_output: {summary['status_output']}")
    print(f"summary_output: {summary['summary_output']}")
    print(f"missing_fields_output: {summary['missing_fields_output']}")

    for record in summary["records"]:
        print()
        print(f"evidence_id: {record.evidence_id}")
        print(f"completion_status: {record.completion_status}")
        print(f"evidence_location_type: {record.proposed_evidence_location_type}")
        print(
            "changed_fields: "
            + (", ".join(record.changed_fields) if record.changed_fields else "none")
        )
        print(
            "missing_exact_fields: "
            + (
                ", ".join(record.missing_exact_fields)
                if record.missing_exact_fields
                else "none"
            )
        )
        print(
            "blocker_reasons: "
            + (
                "; ".join(record.blocker_reasons)
                if record.blocker_reasons
                else "none"
            )
        )
        if record.backup_path:
            print(f"backup_path: {record.backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
