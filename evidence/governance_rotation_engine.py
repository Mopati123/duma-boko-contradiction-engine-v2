#!/usr/bin/env python3
"""
Governance Rotation Engine v1.

Builds candidate-only governance authority rotation validation records.

No evidence approval, readiness escalation, rollback execution,
public release, institutional release, or report publication occurs.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_TEMPLATE_DIR = Path("data/real_evidence_inputs")
DEFAULT_OUTPUT_DIR = Path("outputs/governance_rotation_engine")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_rotation_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_rotation_summary.json"

PROMOTION_STATUS = "verified_for_approval_review"
SAFE_STATUS = "entered_pending_review"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_ROTATION_STATUSES = {
    "rotation_valid_candidate",
    "rotation_not_needed",
    "rotation_blocked",
    "rotation_invalid",
}

ACTIVE_ROTATION = {
    "rotation_id": "GOV_ROTATION_CANDIDATE_V1",
    "rotation_status": "active_candidate",
    "previous_epoch_id": "GOV_EPOCH_CANDIDATE_V1",
    "next_epoch_id": "GOV_EPOCH_CANDIDATE_V1",
    "rotation_mode": "no_rotation_candidate",
    "rotated_out_authorities": [],
    "rotated_in_authorities": [],
    "active_authorities": [
        "AUTH_CANDIDATE_MANUAL_REVIEWER",
        "AUTH_CANDIDATE_GOVERNANCE_REVIEWER",
    ],
}


@dataclass
class GovernanceRotationRecord:
    rotation_record_id: str
    evidence_id: str
    rotation_id: str
    rotation_status: str
    previous_epoch_id: str
    next_epoch_id: str
    rotation_mode: str
    rotated_out_authorities: List[str]
    rotated_in_authorities: List[str]
    active_authorities: List[str]
    rotation_validation_status: str
    rotation_hash: str
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
        "rotation_record_id",
        "evidence_id",
        "rotation_id",
        "rotation_status",
        "previous_epoch_id",
        "next_epoch_id",
        "rotation_mode",
        "rotated_out_authorities",
        "rotated_in_authorities",
        "active_authorities",
        "rotation_validation_status",
        "rotation_hash",
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
        raise ValueError(f"GovernanceRotationRecord missing fields: {sorted(missing)}")

    if data["rotation_validation_status"] not in ALLOWED_ROTATION_STATUSES:
        raise ValueError(
            f"Unsupported rotation_validation_status: {data['rotation_validation_status']}"
        )

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_governance_rotation(
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    if evidence_id:
        template_paths = [DEFAULT_TEMPLATE_DIR / f"{evidence_id}.template.json"]
    else:
        template_paths = sorted(DEFAULT_TEMPLATE_DIR.glob("*.template.json"))

    records: List[GovernanceRotationRecord] = []

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
            rotation_validation_status = "rotation_valid_candidate"
        elif current_status == SAFE_STATUS:
            target_status = SAFE_STATUS
            mutation_summary = f"{current_status}->{current_status}"
            rotation_validation_status = "rotation_not_needed"
        else:
            target_status = current_status
            mutation_summary = f"{current_status}->{current_status}"
            rotation_validation_status = "rotation_blocked"

        rotation_material = json.dumps(
            {
                "evidence_id": record_evidence_id,
                "current_status": current_status,
                "target_status": target_status,
                "mutation_summary": mutation_summary,
                "rotation": ACTIVE_ROTATION,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

        rotation_hash = _sha256_text(rotation_material)

        record = GovernanceRotationRecord(
            rotation_record_id=f"ROTATION_{record_evidence_id}_{rotation_hash[:16]}",
            evidence_id=record_evidence_id,
            rotation_id=ACTIVE_ROTATION["rotation_id"],
            rotation_status=ACTIVE_ROTATION["rotation_status"],
            previous_epoch_id=ACTIVE_ROTATION["previous_epoch_id"],
            next_epoch_id=ACTIVE_ROTATION["next_epoch_id"],
            rotation_mode=ACTIVE_ROTATION["rotation_mode"],
            rotated_out_authorities=list(ACTIVE_ROTATION["rotated_out_authorities"]),
            rotated_in_authorities=list(ACTIVE_ROTATION["rotated_in_authorities"]),
            active_authorities=list(ACTIVE_ROTATION["active_authorities"]),
            rotation_validation_status=rotation_validation_status,
            rotation_hash=rotation_hash,
            current_status=current_status,
            target_status=target_status,
            mutation_summary=mutation_summary,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes=(
                "Candidate-only governance rotation record. No evidence approval, "
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
        "rotation_record_count": len(records),
        "rotation_valid_candidate_count": sum(
            1 for record in records if record.rotation_validation_status == "rotation_valid_candidate"
        ),
        "rotation_not_needed_count": sum(
            1 for record in records if record.rotation_validation_status == "rotation_not_needed"
        ),
        "rotation_blocked_count": sum(
            1 for record in records if record.rotation_validation_status == "rotation_blocked"
        ),
        "rotation_invalid_count": sum(
            1 for record in records if record.rotation_validation_status == "rotation_invalid"
        ),
        "rotation_id": ACTIVE_ROTATION["rotation_id"],
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}