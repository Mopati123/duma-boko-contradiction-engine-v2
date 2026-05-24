"""
final_report_hardening.py - Review-draft hardening metadata.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List
import json

from evidence.evidence_schema import save_json
from evidence.final_report_v1 import (
    DEFAULT_FINAL_REPORT_PAYLOAD,
    generate_final_report_fixture_only,
    validate_final_report_payload,
)
from evidence.manual_review import (
    DEFAULT_MANUAL_REVIEW_SUMMARY_OUTPUT,
    manual_review_dry_run,
)


DEFAULT_FINAL_REPORT_HARDENING_DIR = Path("outputs/final_report_hardening")
DEFAULT_FINAL_REPORT_HARDENING_RECORD = (
    DEFAULT_FINAL_REPORT_HARDENING_DIR / "final_report_hardening_record.json"
)
DEFAULT_FINAL_REPORT_HARDENING_SUMMARY = (
    DEFAULT_FINAL_REPORT_HARDENING_DIR / "final_report_hardening_summary.json"
)

HARDENING_STATUSES = {
    "hardening_candidate",
    "hardened_review_draft",
    "hardening_blocked",
}

RELEASE_STATUSES = {
    "review_draft_only",
    "manual_review_required",
    "blocked_from_public_release",
}

ALLOWED_NEGATED_READINESS_TEXT = (
    "not institution-ready",
)

FORBIDDEN_POSITIVE_READINESS_TEXT = (
    "validated public evidence",
    "final forensic report",
    "proven failure",
    "proven corruption",
    "report_ready",
    "public-ready",
    "public ready",
    "institution-ready",
    "institution ready",
    "ready for public release",
    "ready for institutional release",
)


@dataclass
class FinalReportHardeningRecord:
    hardening_id: str
    report_id: str
    hardening_status: str
    release_status: str
    methodology_note: str
    limitations_note: str
    evidence_status_summary: Dict[str, Any]
    manual_review_summary: Dict[str, Any]
    source_index: List[Dict[str, Any]]
    audit_trail_summary: List[str]
    ci_validation_note: str
    github_actions_note: str
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    hardening_notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_dict(value: Any) -> Dict[str, Any]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    raise ValueError(f"Expected object or dict, got {type(value).__name__}")


def _string_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _string_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _string_values(item)


def _require_nonempty_string(data: Dict[str, Any], field_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"FinalReportHardeningRecord.{field_name} must be a non-empty string"
        )


def _require_nonempty_mapping(data: Dict[str, Any], field_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, dict) or not value:
        raise ValueError(
            f"FinalReportHardeningRecord.{field_name} must be a non-empty object"
        )


def _require_nonempty_list(data: Dict[str, Any], field_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, list) or not value:
        raise ValueError(
            f"FinalReportHardeningRecord.{field_name} must be a non-empty list"
        )


def _remove_allowed_negated_readiness(text: str) -> str:
    sanitized = text.lower()
    for phrase in ALLOWED_NEGATED_READINESS_TEXT:
        sanitized = sanitized.replace(phrase, "")
    return sanitized


def _reject_positive_readiness_claims(data: Dict[str, Any]) -> None:
    text = _remove_allowed_negated_readiness("\n".join(_string_values(data)))
    for phrase in FORBIDDEN_POSITIVE_READINESS_TEXT:
        if phrase in text:
            raise ValueError(
                "FinalReportHardeningRecord contains prohibited readiness claim: "
                f"{phrase}"
            )


def validate_final_report_hardening_record(record: Any) -> None:
    data = _as_dict(record)

    for field_name in (
        "hardening_id",
        "report_id",
        "hardening_status",
        "release_status",
        "methodology_note",
        "limitations_note",
        "ci_validation_note",
        "github_actions_note",
        "hardening_notes",
    ):
        _require_nonempty_string(data, field_name)

    _require_nonempty_mapping(data, "evidence_status_summary")
    _require_nonempty_mapping(data, "manual_review_summary")
    _require_nonempty_list(data, "source_index")
    _require_nonempty_list(data, "audit_trail_summary")

    if data["hardening_status"] not in HARDENING_STATUSES:
        raise ValueError(
            "FinalReportHardeningRecord.hardening_status is unsupported: "
            f"{data['hardening_status']}"
        )
    if data["release_status"] not in RELEASE_STATUSES:
        raise ValueError(
            "FinalReportHardeningRecord.release_status is unsupported: "
            f"{data['release_status']}"
        )

    if data.get("public_ready") is not False:
        raise ValueError("FinalReportHardeningRecord.public_ready must be false")
    if data.get("institutional_ready") is not False:
        raise ValueError(
            "FinalReportHardeningRecord.institutional_ready must be false"
        )
    if data.get("report_ready") is not False:
        raise ValueError("FinalReportHardeningRecord.report_ready must be false")

    if data["hardening_status"] == "hardening_blocked":
        if "reason" not in data["hardening_notes"].lower():
            raise ValueError(
                "FinalReportHardeningRecord.hardening_blocked requires a reason "
                "in hardening_notes"
            )

    _reject_positive_readiness_claims(data)


def _load_final_report_payload(path: Path = DEFAULT_FINAL_REPORT_PAYLOAD) -> Dict[str, Any]:
    if not path.exists():
        generate_final_report_fixture_only()

    artifact = json.loads(path.read_text(encoding="utf-8"))
    payload = artifact.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Final report payload artifact must contain payload")
    validate_final_report_payload(payload)
    return payload


def _load_manual_review_summary(
    path: Path = DEFAULT_MANUAL_REVIEW_SUMMARY_OUTPUT,
) -> Dict[str, Any]:
    if not path.exists():
        manual_review_dry_run()

    summary = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(summary, dict) or not summary:
        raise ValueError("Manual review summary artifact must be a non-empty object")
    return summary


def build_final_report_hardening_record_dry_run() -> FinalReportHardeningRecord:
    payload = _load_final_report_payload()
    manual_summary = _load_manual_review_summary()
    sections = payload["sections"]
    evidence_ids = sorted(
        {
            evidence_id
            for section in sections
            for evidence_id in section.get("evidence_ids", [])
        }
    )

    source_index = [
        {
            "section_id": section["section_id"],
            "case_id": section["case_id"],
            "claim_ids": section["claim_ids"],
            "evidence_ids": section["evidence_ids"],
            "fixture_notice": "Fixture/test evidence may be present.",
        }
        for section in sections
    ]

    record = FinalReportHardeningRecord(
        hardening_id="FINAL_REPORT_HARDENING_V1_DRY_RUN",
        report_id=str(payload["report_id"]),
        hardening_status="hardened_review_draft",
        release_status="manual_review_required",
        methodology_note=(
            "Review draft only. The hardening dry-run adds methodology, evidence "
            "status, source index, manual review, and audit context without changing "
            "evidence readiness."
        ),
        limitations_note=(
            "Not for public release. Fixture/test evidence may be present. "
            "Manual review required. Not institution-ready. Evidence conclusions "
            "require real transcript, timestamp, quote, and context approval."
        ),
        evidence_status_summary={
            "sections_included": len(sections),
            "evidence_ids_represented": len(evidence_ids),
            "evidence_ids": evidence_ids,
            "fixture_or_dry_run_mode": True,
        },
        manual_review_summary={
            "total_evidence_records_reviewed": manual_summary.get(
                "total_evidence_records_reviewed", 0
            ),
            "pending_review": manual_summary.get("pending_review", 0),
            "public_ready": manual_summary.get("public_ready", 0),
            "report_ready": manual_summary.get("report_ready", 0),
            "manual_review_required": manual_summary.get(
                "manual_review_required", 0
            ),
        },
        source_index=source_index,
        audit_trail_summary=[
            "Evidence Gate v1 remains active.",
            "Local CI passed before this dry-run hardening artifact is reviewable.",
            "Manual Review v1 remains conservative and non-public.",
        ],
        ci_validation_note=(
            "Local CI is the validation authority while GitHub Actions is "
            "unavailable; no public release status is set."
        ),
        github_actions_note=(
            "GitHub Actions unavailable due to account/billing lock; local CI used "
            "as validation authority."
        ),
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        hardening_notes=(
            "Dry-run hardening record only. Review draft remains blocked from public "
            "release until real-source evidence and manual approval replace fixtures."
        ),
    )
    validate_final_report_hardening_record(record)
    return record


def write_final_report_hardening_outputs(
    record: FinalReportHardeningRecord,
    output_dir: Path = DEFAULT_FINAL_REPORT_HARDENING_DIR,
) -> Dict[str, str]:
    validate_final_report_hardening_record(record)
    output_dir.mkdir(parents=True, exist_ok=True)

    record_path = output_dir / "final_report_hardening_record.json"
    summary_path = output_dir / "final_report_hardening_summary.json"
    summary = {
        "generated_at_utc": utc_now_iso(),
        "mode": "dry-run",
        "hardening_id": record.hardening_id,
        "report_id": record.report_id,
        "hardening_status": record.hardening_status,
        "release_status": record.release_status,
        "public_ready": record.public_ready,
        "institutional_ready": record.institutional_ready,
        "report_ready": record.report_ready,
        "record_output": str(record_path),
        "summary_output": str(summary_path),
    }

    save_json(
        {
            "metadata": {
                "generated_at_utc": utc_now_iso(),
                "mode": "dry-run",
                "public_ready": False,
                "institutional_ready": False,
                "report_ready": False,
            },
            "record": record.to_dict(),
        },
        str(record_path),
    )
    save_json(summary, str(summary_path))
    return {
        "record_output": str(record_path),
        "summary_output": str(summary_path),
    }


def harden_final_report_dry_run(
    output_dir: Path = DEFAULT_FINAL_REPORT_HARDENING_DIR,
) -> Dict[str, Any]:
    record = build_final_report_hardening_record_dry_run()
    outputs = write_final_report_hardening_outputs(record, output_dir)
    return {
        "hardening_id": record.hardening_id,
        "report_id": record.report_id,
        "hardening_status": record.hardening_status,
        "release_status": record.release_status,
        "public_ready": record.public_ready,
        "institutional_ready": record.institutional_ready,
        "report_ready": record.report_ready,
        "record": record,
        **outputs,
    }
