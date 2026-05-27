#!/usr/bin/env python3
"""
Explicit template reconciliation action lane.

This lane performs governed reconciliation rollback from:
verified_for_approval_review
→ entered_pending_review

Default mode is dry-run.
No approval or readiness transitions are allowed.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import shutil


DEFAULT_TEMPLATE_DIR = Path("data/real_evidence_inputs")
DEFAULT_OUTPUT_DIR = Path("outputs/template_reconciliation_action")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "template_reconciliation_action_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "template_reconciliation_action_summary.json"

PROMOTION_STATUS = "verified_for_approval_review"
SAFE_STATUS = "entered_pending_review"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_ACTION_STATUSES = {
    "would_reconcile_to_entered_pending_review",
    "reconciled_to_entered_pending_review",
    "no_action_needed",
    "blocked_manual_review",
}


@dataclass
class TemplateReconciliationActionRecord:
    evidence_id: str
    template_path: str
    previous_status: str
    new_status: str
    action_status: str
    action_reason: str
    write_applied: bool
    backup_path: str
    approved_evidence: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    requires_manual_review: bool
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "evidence_id",
        "template_path",
        "previous_status",
        "new_status",
        "action_status",
        "action_reason",
        "write_applied",
        "backup_path",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"TemplateReconciliationActionRecord missing fields: {sorted(missing)}")

    if data["action_status"] not in ALLOWED_ACTION_STATUSES:
        raise ValueError(
            f"Unsupported action_status: {data['action_status']}"
        )

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def reconcile_template(
    template_path: Path,
    write: bool = False,
) -> TemplateReconciliationActionRecord:

    payload = _load_json(template_path)

    evidence_id = payload.get(
        "evidence_id",
        template_path.stem.replace(".template", ""),
    )

    current_status = payload.get("verification_status", "unknown")

    backup_path = ""

    if current_status == PROMOTION_STATUS:

        if write:
            DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            backup = (
                DEFAULT_OUTPUT_DIR
                / f"{template_path.name}.backup.json"
            )

            shutil.copy2(template_path, backup)

            payload["verification_status"] = SAFE_STATUS

            _write_json(template_path, payload)

            action_status = "reconciled_to_entered_pending_review"
            write_applied = True
            backup_path = str(backup)

        else:
            action_status = "would_reconcile_to_entered_pending_review"
            write_applied = False

        new_status = SAFE_STATUS

        action_reason = (
            "Illegal early promotion state detected. "
            "Template must be reconciled back to entered_pending_review."
        )

    elif current_status == SAFE_STATUS:

        action_status = "no_action_needed"
        write_applied = False
        new_status = SAFE_STATUS

        action_reason = (
            "Template already in lawful pre-promotion state."
        )

    else:

        action_status = "blocked_manual_review"
        write_applied = False
        new_status = current_status

        action_reason = (
            "Template status requires manual governance review."
        )

    record = TemplateReconciliationActionRecord(
        evidence_id=evidence_id,
        template_path=str(template_path),
        previous_status=current_status,
        new_status=new_status,
        action_status=action_status,
        action_reason=action_reason,
        write_applied=write_applied,
        backup_path=backup_path,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Governed reconciliation action only. "
            "No evidence approval, readiness escalation, "
            "quote generation, transcript generation, "
            "timestamp generation, or report generation occurred."
        ),
    )

    validate_record(record)

    return record


def run_reconciliation(
    evidence_id: Optional[str] = None,
    write: bool = False,
) -> Dict[str, Any]:

    if evidence_id:
        template_paths = [
            DEFAULT_TEMPLATE_DIR / f"{evidence_id}.template.json"
        ]
    else:
        template_paths = sorted(
            DEFAULT_TEMPLATE_DIR.glob("*.template.json")
        )

    records: List[TemplateReconciliationActionRecord] = []

    for template_path in template_paths:

        if not template_path.exists():
            continue

        records.append(
            reconcile_template(
                template_path=template_path,
                write=write,
            )
        )

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "records": [r.to_dict() for r in records]
    }

    summary = {
        "record_count": len(records),
        "would_reconcile_count": sum(
            1
            for r in records
            if r.action_status == "would_reconcile_to_entered_pending_review"
        ),
        "reconciled_count": sum(
            1
            for r in records
            if r.action_status == "reconciled_to_entered_pending_review"
        ),
        "no_action_needed_count": sum(
            1
            for r in records
            if r.action_status == "no_action_needed"
        ),
        "blocked_manual_review_count": sum(
            1
            for r in records
            if r.action_status == "blocked_manual_review"
        ),
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {
        "payload": payload,
        "summary": summary,
    }