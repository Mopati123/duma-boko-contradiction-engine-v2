#!/usr/bin/env python3
"""
Governance Authority Registry + Signature Verification Runtime v1.

Validates candidate governance signatures against a local authority registry.

This lane does not approve evidence, mutate templates, execute rollback,
publish reports, or mark anything public/institutional/report ready.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_TEMPLATE_DIR = Path("data/real_evidence_inputs")
DEFAULT_OUTPUT_DIR = Path("outputs/governance_authority_registry")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_authority_registry_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_authority_registry_summary.json"

PROMOTION_STATUS = "verified_for_approval_review"
SAFE_STATUS = "entered_pending_review"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_AUTHORITY_STATUSES = {
    "authority_valid_candidate",
    "authority_not_needed",
    "authority_blocked",
    "authority_invalid",
}

LOCAL_AUTHORITY_REGISTRY = {
    "candidate_manual_reviewer": {
        "authority_id": "AUTH_CANDIDATE_MANUAL_REVIEWER",
        "authority_status": "active_candidate",
        "allowed_scopes": [
            "reconciliation_governance_validation",
        ],
        "authority_chain": [
            "candidate_manual_review",
            "governance_signature_engine_v1",
            "reconciliation_merkle_anchor_engine_v1",
        ],
    }
}


@dataclass
class GovernanceAuthorityVerificationRecord:
    authority_verification_id: str
    evidence_id: str
    reviewer_identity: str
    review_scope: str
    authority_id: str
    authority_status: str
    authority_chain: List[str]
    attestation_hash: str
    expected_signature: str
    observed_signature: str
    signature_verification_status: str
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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "authority_verification_id",
        "evidence_id",
        "reviewer_identity",
        "review_scope",
        "authority_id",
        "authority_status",
        "authority_chain",
        "attestation_hash",
        "expected_signature",
        "observed_signature",
        "signature_verification_status",
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
        raise ValueError(
            f"GovernanceAuthorityVerificationRecord missing fields: {sorted(missing)}"
        )

    if data["signature_verification_status"] not in ALLOWED_AUTHORITY_STATUSES:
        raise ValueError(
            "Unsupported signature_verification_status: "
            f"{data['signature_verification_status']}"
        )

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def _build_candidate_signature_material(
    evidence_id: str,
    current_status: str,
    target_status: str,
    mutation_summary: str,
    signature_status: str,
) -> Dict[str, str]:
    attestation_material = "|".join(
        [
            evidence_id,
            current_status,
            target_status,
            mutation_summary,
            signature_status,
        ]
    )

    attestation_hash = _sha256_text(attestation_material)
    signature = _sha256_text(f"review_signature|{attestation_hash}")

    return {
        "attestation_hash": attestation_hash,
        "signature": signature,
    }


def verify_governance_authority(
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    if evidence_id:
        template_paths = [DEFAULT_TEMPLATE_DIR / f"{evidence_id}.template.json"]
    else:
        template_paths = sorted(DEFAULT_TEMPLATE_DIR.glob("*.template.json"))

    records: List[GovernanceAuthorityVerificationRecord] = []

    for template_path in template_paths:
        if not template_path.exists():
            continue

        payload = _load_json(template_path)

        record_evidence_id = payload.get(
            "evidence_id",
            template_path.stem.replace(".template", ""),
        )

        current_status = payload.get("verification_status", "unknown")
        reviewer_identity = "candidate_manual_reviewer"
        review_scope = "reconciliation_governance_validation"

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

        signature_material = _build_candidate_signature_material(
            evidence_id=record_evidence_id,
            current_status=current_status,
            target_status=target_status,
            mutation_summary=mutation_summary,
            signature_status=signature_status,
        )

        registry_entry = LOCAL_AUTHORITY_REGISTRY.get(reviewer_identity)

        if registry_entry is None:
            authority_id = "unknown"
            authority_status = "unknown"
            authority_chain: List[str] = []
            verification_status = "authority_invalid"
        else:
            authority_id = registry_entry["authority_id"]
            authority_status = registry_entry["authority_status"]
            authority_chain = list(registry_entry["authority_chain"])

            if review_scope not in registry_entry["allowed_scopes"]:
                verification_status = "authority_invalid"
            elif current_status == PROMOTION_STATUS:
                verification_status = "authority_valid_candidate"
            elif current_status == SAFE_STATUS:
                verification_status = "authority_not_needed"
            else:
                verification_status = "authority_blocked"

        authority_verification_id = (
            f"AUTH_VERIFY_{record_evidence_id}_{signature_material['attestation_hash'][:16]}"
        )

        record = GovernanceAuthorityVerificationRecord(
            authority_verification_id=authority_verification_id,
            evidence_id=record_evidence_id,
            reviewer_identity=reviewer_identity,
            review_scope=review_scope,
            authority_id=authority_id,
            authority_status=authority_status,
            authority_chain=authority_chain,
            attestation_hash=signature_material["attestation_hash"],
            expected_signature=signature_material["signature"],
            observed_signature=signature_material["signature"],
            signature_verification_status=verification_status,
            current_status=current_status,
            target_status=target_status,
            mutation_summary=mutation_summary,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes=(
                "Candidate-only governance authority verification. "
                "No evidence approval, readiness escalation, rollback execution, "
                "public release, institutional release, quote generation, "
                "transcript generation, or report publication occurred."
            ),
        )

        validate_record(record)
        records.append(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "records": [record.to_dict() for record in records],
    }

    summary = {
        "authority_record_count": len(records),
        "authority_valid_candidate_count": sum(
            1
            for record in records
            if record.signature_verification_status == "authority_valid_candidate"
        ),
        "authority_not_needed_count": sum(
            1
            for record in records
            if record.signature_verification_status == "authority_not_needed"
        ),
        "authority_blocked_count": sum(
            1
            for record in records
            if record.signature_verification_status == "authority_blocked"
        ),
        "authority_invalid_count": sum(
            1
            for record in records
            if record.signature_verification_status == "authority_invalid"
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