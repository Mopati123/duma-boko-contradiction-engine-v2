#!/usr/bin/env python3
"""
Governance Epoch Engine v1.

Builds candidate-only governance epoch validation records.

No evidence approval, readiness escalation, rollback execution,
public release, institutional release, or report publication occurs.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_TEMPLATE_DIR = Path("data/real_evidence_inputs")
DEFAULT_OUTPUT_DIR = Path("outputs/governance_epoch_engine")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_epoch_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_epoch_summary.json"

PROMOTION_STATUS = "verified_for_approval_review"
SAFE_STATUS = "entered_pending_review"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_EPOCH_STATUSES = {
    "epoch_valid_candidate",
    "epoch_not_needed",
    "epoch_blocked",
    "epoch_invalid",
}

ACTIVE_EPOCH = {
    "epoch_id": "GOV_EPOCH_CANDIDATE_V1",
    "epoch_status": "active_candidate",
    "authority_activation": "candidate_active",
    "authority_expiration": "not_set_candidate",
    "authority_revocation": "not_revoked",
    "authority_rotation": "not_rotated",
    "allowed_authorities": [
        "AUTH_CANDIDATE_MANUAL_REVIEWER",
        "AUTH_CANDIDATE_GOVERNANCE_REVIEWER",
    ],
}


@dataclass
class GovernanceEpochRecord:
    epoch_record_id: str
    evidence_id: str
    epoch_id: str
    epoch_status: str
    authority_activation: str
    authority_expiration: str
    authority_revocation: str
    authority_rotation: str
    epoch_authorities: List[str]
    epoch_validation_status: str
    epoch_hash: str
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
        "epoch_record_id",
        "evidence_id",
        "epoch_id",
        "epoch_status",
        "authority_activation",
        "authority_expiration",
        "authority_revocation",
        "authority_rotation",
        "epoch_authorities",
        "epoch_validation_status",
        "epoch_hash",
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
        raise ValueError(f"GovernanceEpochRecord missing fields: {sorted(missing)}")

    if data["epoch_validation_status"] not in ALLOWED_EPOCH_STATUSES:
        raise ValueError(f"Unsupported epoch_validation_status: {data['epoch_validation_status']}")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_governance_epoch(
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    if evidence_id:
        template_paths = [DEFAULT_TEMPLATE_DIR / f"{evidence_id}.template.json"]
    else:
        template_paths = sorted(DEFAULT_TEMPLATE_DIR.glob("*.template.json"))

    records: List[GovernanceEpochRecord] = []

    for template_path in template_paths:
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
            epoch_validation_status = "epoch_valid_candidate"
        elif current_status == SAFE_STATUS:
            target_status = SAFE_STATUS
            mutation_summary = f"{current_status}->{current_status}"
            epoch_validation_status = "epoch_not_needed"
        else:
            target_status = current_status
            mutation_summary = f"{current_status}->{current_status}"
            epoch_validation_status = "epoch_blocked"

        epoch_material = json.dumps(
            {
                "evidence_id": record_evidence_id,
                "current_status": current_status,
                "target_status": target_status,
                "mutation_summary": mutation_summary,
                "epoch": ACTIVE_EPOCH,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

        epoch_hash = _sha256_text(epoch_material)

        record = GovernanceEpochRecord(
            epoch_record_id=f"EPOCH_{record_evidence_id}_{epoch_hash[:16]}",
            evidence_id=record_evidence_id,
            epoch_id=ACTIVE_EPOCH["epoch_id"],
            epoch_status=ACTIVE_EPOCH["epoch_status"],
            authority_activation=ACTIVE_EPOCH["authority_activation"],
            authority_expiration=ACTIVE_EPOCH["authority_expiration"],
            authority_revocation=ACTIVE_EPOCH["authority_revocation"],
            authority_rotation=ACTIVE_EPOCH["authority_rotation"],
            epoch_authorities=list(ACTIVE_EPOCH["allowed_authorities"]),
            epoch_validation_status=epoch_validation_status,
            epoch_hash=epoch_hash,
            current_status=current_status,
            target_status=target_status,
            mutation_summary=mutation_summary,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes=(
                "Candidate-only governance epoch record. No evidence approval, "
                "readiness escalation, rollback execution, public release, "
                "institutional release, quote generation, transcript generation, "
                "or report publication occurred."
            ),
        )

        validate_record(record)
        records.append(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    summary = {
        "epoch_record_count": len(records),
        "epoch_valid_candidate_count": sum(
            1 for record in records if record.epoch_validation_status == "epoch_valid_candidate"
        ),
        "epoch_not_needed_count": sum(
            1 for record in records if record.epoch_validation_status == "epoch_not_needed"
        ),
        "epoch_blocked_count": sum(
            1 for record in records if record.epoch_validation_status == "epoch_blocked"
        ),
        "epoch_invalid_count": sum(
            1 for record in records if record.epoch_validation_status == "epoch_invalid"
        ),
        "epoch_id": ACTIVE_EPOCH["epoch_id"],
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}