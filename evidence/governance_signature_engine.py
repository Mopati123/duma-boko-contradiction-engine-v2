#!/usr/bin/env python3

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_TEMPLATE_DIR = Path("data/real_evidence_inputs")
DEFAULT_OUTPUT_DIR = Path("outputs/governance_signatures")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_signature_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_signature_summary.json"

PROMOTION_STATUS = "verified_for_approval_review"
SAFE_STATUS = "entered_pending_review"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_SIGNATURE_STATUSES = {
    "signature_candidate",
    "signature_not_needed",
    "signature_blocked",
}


@dataclass
class GovernanceSignatureRecord:
    signature_id: str
    evidence_id: str
    reviewer_identity: str
    review_scope: str
    authority_chain: List[str]
    attestation_hash: str
    review_signature: str
    signature_status: str
    current_status: str
    target_status: str
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
        "signature_id",
        "evidence_id",
        "reviewer_identity",
        "review_scope",
        "authority_chain",
        "attestation_hash",
        "review_signature",
        "signature_status",
        "current_status",
        "target_status",
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
        raise ValueError(f"GovernanceSignatureRecord missing fields: {sorted(missing)}")

    if data["signature_status"] not in ALLOWED_SIGNATURE_STATUSES:
        raise ValueError(
            f"Unsupported signature_status: {data['signature_status']}"
        )

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_governance_signatures(
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:

    if evidence_id:
        template_paths = [DEFAULT_TEMPLATE_DIR / f"{evidence_id}.template.json"]
    else:
        template_paths = sorted(DEFAULT_TEMPLATE_DIR.glob("*.template.json"))

    records: List[GovernanceSignatureRecord] = []

    for template_path in template_paths:
        if not template_path.exists():
            continue

        payload = _load_json(template_path)

        current_status = payload.get("verification_status", "unknown")

        record_evidence_id = payload.get(
            "evidence_id",
            template_path.stem.replace(".template", ""),
        )

        if current_status == PROMOTION_STATUS:
            target_status = SAFE_STATUS
            mutation_summary = f"{current_status}->{SAFE_STATUS}"
            signature_status = "signature_candidate"
        elif current_status == SAFE_STATUS:
            target_status = SAFE_STATUS
            mutation_summary = f"{current_status}->{current_status}"
            signature_status = "signature_not_needed"
        else:
            target_status = current_status
            mutation_summary = f"{current_status}->{current_status}"
            signature_status = "signature_blocked"

        attestation_material = "|".join(
            [
                record_evidence_id,
                current_status,
                target_status,
                mutation_summary,
                signature_status,
            ]
        )

        attestation_hash = _sha256_text(attestation_material)

        review_signature = _sha256_text(
            f"review_signature|{attestation_hash}"
        )

        signature_id = f"GOV_SIG_{attestation_hash[:16]}"

        record = GovernanceSignatureRecord(
            signature_id=signature_id,
            evidence_id=record_evidence_id,
            reviewer_identity="candidate_manual_reviewer",
            review_scope="reconciliation_governance_validation",
            authority_chain=[
                "candidate_manual_review",
                "governance_signature_engine_v1",
                "reconciliation_merkle_anchor_engine_v1",
            ],
            attestation_hash=attestation_hash,
            review_signature=review_signature,
            signature_status=signature_status,
            current_status=current_status,
            target_status=target_status,
            mutation_summary=mutation_summary,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes=(
                "Candidate-only governance signature record. "
                "No rollback execution, evidence approval, readiness escalation, "
                "public release, institutional release, transcript generation, "
                "quote generation, or report publication occurred."
            ),
        )

        validate_record(record)
        records.append(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "records": [record.to_dict() for record in records],
    }

    summary = {
        "signature_record_count": len(records),
        "signature_candidate_count": sum(
            1
            for record in records
            if record.signature_status == "signature_candidate"
        ),
        "signature_not_needed_count": sum(
            1
            for record in records
            if record.signature_status == "signature_not_needed"
        ),
        "signature_blocked_count": sum(
            1
            for record in records
            if record.signature_status == "signature_blocked"
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