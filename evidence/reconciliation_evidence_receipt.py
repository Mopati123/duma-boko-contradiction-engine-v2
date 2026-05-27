#!/usr/bin/env python3
"""
Reconciliation Evidence Receipt Engine v1.

Build immutable candidate-only receipts for reconciliation execution events.

This lane does not execute rollback.
It only emits receipt-grade evidence artifacts.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json
import time


DEFAULT_TEMPLATE_DIR = Path("data/real_evidence_inputs")
DEFAULT_OUTPUT_DIR = Path("outputs/reconciliation_evidence_receipts")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "reconciliation_evidence_receipts_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "reconciliation_evidence_receipts_summary.json"

PROMOTION_STATUS = "verified_for_approval_review"
SAFE_STATUS = "entered_pending_review"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_RECEIPT_STATUSES = {
    "would_emit_reconciliation_receipt",
    "receipt_not_needed",
    "receipt_blocked",
}


@dataclass
class ReconciliationEvidenceReceipt:
    receipt_id: str
    evidence_id: str
    template_path: str
    current_status: str
    target_status: str
    receipt_status: str
    execution_hash: str
    template_hash_before: str
    template_hash_after: str
    backup_hash: str
    mutation_summary: str
    execution_operator: str
    execution_timestamp: str
    approved_evidence: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    requires_manual_review: bool
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def validate_receipt(receipt: Any) -> None:
    data = receipt.to_dict() if hasattr(receipt, "to_dict") else receipt

    required = {
        "receipt_id",
        "evidence_id",
        "template_path",
        "current_status",
        "target_status",
        "receipt_status",
        "execution_hash",
        "template_hash_before",
        "template_hash_after",
        "backup_hash",
        "mutation_summary",
        "execution_operator",
        "execution_timestamp",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"ReconciliationEvidenceReceipt missing fields: {sorted(missing)}")

    if data["receipt_status"] not in ALLOWED_RECEIPT_STATUSES:
        raise ValueError(f"Unsupported receipt_status: {data['receipt_status']}")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_receipt(template_path: Path) -> ReconciliationEvidenceReceipt:
    payload = _load_json(template_path)

    evidence_id = payload.get(
        "evidence_id",
        template_path.stem.replace(".template", ""),
    )

    current_status = payload.get("verification_status", "unknown")
    timestamp = str(int(time.time()))
    template_hash_before = _sha256_bytes(_read_bytes(template_path))

    mutation_summary = (
        f"{current_status}->{SAFE_STATUS}"
        if current_status == PROMOTION_STATUS
        else f"{current_status}->{current_status}"
    )

    execution_hash = _sha256_text(
        f"{evidence_id}|{template_hash_before}|{mutation_summary}"
    )

    receipt_id = f"RECON_RECEIPT_{evidence_id}_{execution_hash[:16]}"

    if current_status == PROMOTION_STATUS:
        receipt_status = "would_emit_reconciliation_receipt"
        target_status = SAFE_STATUS
        template_hash_after = "pending_execution"
        backup_hash = "pending_execution_backup"
    elif current_status == SAFE_STATUS:
        receipt_status = "receipt_not_needed"
        target_status = SAFE_STATUS
        template_hash_after = template_hash_before
        backup_hash = "not_applicable"
    else:
        receipt_status = "receipt_blocked"
        target_status = current_status
        template_hash_after = template_hash_before
        backup_hash = "not_applicable"

    receipt = ReconciliationEvidenceReceipt(
        receipt_id=receipt_id,
        evidence_id=evidence_id,
        template_path=str(template_path),
        current_status=current_status,
        target_status=target_status,
        receipt_status=receipt_status,
        execution_hash=execution_hash,
        template_hash_before=template_hash_before,
        template_hash_after=template_hash_after,
        backup_hash=backup_hash,
        mutation_summary=mutation_summary,
        execution_operator="ReconciliationExecutionEngine.v1",
        execution_timestamp=timestamp,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Candidate-only reconciliation evidence receipt. "
            "No rollback execution, approval, readiness escalation, quote generation, "
            "transcript generation, timestamp generation, or report generation occurred."
        ),
    )

    validate_receipt(receipt)
    return receipt


def build_receipts(
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    if evidence_id:
        template_paths = [DEFAULT_TEMPLATE_DIR / f"{evidence_id}.template.json"]
    else:
        template_paths = sorted(DEFAULT_TEMPLATE_DIR.glob("*.template.json"))

    receipts: List[ReconciliationEvidenceReceipt] = []

    for template_path in template_paths:
        if not template_path.exists():
            continue
        receipts.append(build_receipt(template_path))

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "records": [receipt.to_dict() for receipt in receipts],
    }

    summary = {
        "receipt_count": len(receipts),
        "would_emit_receipt_count": sum(
            1
            for receipt in receipts
            if receipt.receipt_status == "would_emit_reconciliation_receipt"
        ),
        "receipt_not_needed_count": sum(
            1
            for receipt in receipts
            if receipt.receipt_status == "receipt_not_needed"
        ),
        "receipt_blocked_count": sum(
            1
            for receipt in receipts
            if receipt.receipt_status == "receipt_blocked"
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