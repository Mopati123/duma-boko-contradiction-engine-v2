#!/usr/bin/env python3
"""
Reconciliation Hash Chain Engine v1.

Builds tamper-evident hash-chain records over reconciliation receipt candidates.

This lane does not approve evidence, mutate templates, execute rollback,
or mark anything public/institutional/report ready.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_TEMPLATE_DIR = Path("data/real_evidence_inputs")
DEFAULT_OUTPUT_DIR = Path("outputs/reconciliation_hash_chain")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "reconciliation_hash_chain_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "reconciliation_hash_chain_summary.json"

PROMOTION_STATUS = "verified_for_approval_review"
SAFE_STATUS = "entered_pending_review"
GENESIS_HASH = "0" * 64

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_CHAIN_STATUSES = {
    "chain_candidate",
    "chain_not_needed",
    "chain_blocked",
}


@dataclass
class ReconciliationHashChainRecord:
    receipt_sequence_number: int
    evidence_id: str
    template_path: str
    current_status: str
    target_status: str
    previous_receipt_hash: str
    current_receipt_hash: str
    receipt_chain_root: str
    chain_integrity_status: str
    mutation_summary: str
    approved_evidence: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    requires_manual_review: bool
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "receipt_sequence_number",
        "evidence_id",
        "template_path",
        "current_status",
        "target_status",
        "previous_receipt_hash",
        "current_receipt_hash",
        "receipt_chain_root",
        "chain_integrity_status",
        "mutation_summary",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"ReconciliationHashChainRecord missing fields: {sorted(missing)}")

    if data["chain_integrity_status"] not in ALLOWED_CHAIN_STATUSES:
        raise ValueError(f"Unsupported chain_integrity_status: {data['chain_integrity_status']}")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def _build_receipt_hash_material(
    evidence_id: str,
    template_path: str,
    current_status: str,
    target_status: str,
    mutation_summary: str,
    previous_receipt_hash: str,
    sequence_number: int,
) -> str:
    return "|".join(
        [
            str(sequence_number),
            evidence_id,
            template_path,
            current_status,
            target_status,
            mutation_summary,
            previous_receipt_hash,
        ]
    )


def build_hash_chain(
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    if evidence_id:
        template_paths = [DEFAULT_TEMPLATE_DIR / f"{evidence_id}.template.json"]
    else:
        template_paths = sorted(DEFAULT_TEMPLATE_DIR.glob("*.template.json"))

    records: List[ReconciliationHashChainRecord] = []
    previous_hash = GENESIS_HASH

    for sequence_number, template_path in enumerate(template_paths, start=1):
        if not template_path.exists():
            continue

        payload = _load_json(template_path)

        record_evidence_id = payload.get(
            "evidence_id",
            template_path.stem.replace(".template", ""),
        )

        current_status = payload.get("verification_status", "unknown")

        if current_status == PROMOTION_STATUS:
            target_status = SAFE_STATUS
            mutation_summary = f"{current_status}->{SAFE_STATUS}"
            chain_integrity_status = "chain_candidate"
        elif current_status == SAFE_STATUS:
            target_status = SAFE_STATUS
            mutation_summary = f"{current_status}->{current_status}"
            chain_integrity_status = "chain_not_needed"
        else:
            target_status = current_status
            mutation_summary = f"{current_status}->{current_status}"
            chain_integrity_status = "chain_blocked"

        material = _build_receipt_hash_material(
            evidence_id=record_evidence_id,
            template_path=str(template_path),
            current_status=current_status,
            target_status=target_status,
            mutation_summary=mutation_summary,
            previous_receipt_hash=previous_hash,
            sequence_number=sequence_number,
        )

        current_hash = _sha256_text(material)
        chain_root = _sha256_text(f"{previous_hash}|{current_hash}")

        record = ReconciliationHashChainRecord(
            receipt_sequence_number=sequence_number,
            evidence_id=record_evidence_id,
            template_path=str(template_path),
            current_status=current_status,
            target_status=target_status,
            previous_receipt_hash=previous_hash,
            current_receipt_hash=current_hash,
            receipt_chain_root=chain_root,
            chain_integrity_status=chain_integrity_status,
            mutation_summary=mutation_summary,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes=(
                "Candidate-only reconciliation hash-chain record. "
                "No rollback execution, evidence approval, readiness escalation, "
                "quote generation, transcript generation, timestamp generation, "
                "or report generation occurred."
            ),
        )

        validate_record(record)
        records.append(record)
        previous_hash = chain_root

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    summary = {
        "chain_record_count": len(records),
        "chain_candidate_count": sum(
            1 for record in records if record.chain_integrity_status == "chain_candidate"
        ),
        "chain_not_needed_count": sum(
            1 for record in records if record.chain_integrity_status == "chain_not_needed"
        ),
        "chain_blocked_count": sum(
            1 for record in records if record.chain_integrity_status == "chain_blocked"
        ),
        "receipt_chain_root": records[-1].receipt_chain_root if records else GENESIS_HASH,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}