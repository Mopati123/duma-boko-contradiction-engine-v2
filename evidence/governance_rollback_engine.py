#!/usr/bin/env python3
"""
Governance Rollback Engine v1.

Builds candidate-only rollback admissibility records.

Rollback is represented as a deterministic reversal candidate, not as an
executed mutation. No evidence approval, readiness escalation, public release,
institutional release, or report publication occurs.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional, List
import hashlib
import json


DEFAULT_TEMPLATE_DIR = Path("data/real_evidence_inputs")
DEFAULT_OUTPUT_DIR = Path("outputs/governance_rollback_engine")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_rollback_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_rollback_summary.json"

PROMOTION_STATUS = "verified_for_approval_review"
SAFE_STATUS = "entered_pending_review"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "rollback_executed",
)

ALLOWED_ROLLBACK_STATUSES = {
    "rollback_candidate",
    "rollback_not_needed",
    "rollback_blocked",
    "rollback_invalid",
}


@dataclass
class GovernanceRollbackRecord:
    rollback_id: str
    evidence_id: str
    rollback_status: str
    rollback_surfaces: Dict[str, str]
    rollback_hash: str
    current_status: str
    target_status: str
    reversal_status: str
    rollback_executed: bool
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
        "rollback_id",
        "evidence_id",
        "rollback_status",
        "rollback_surfaces",
        "rollback_hash",
        "current_status",
        "target_status",
        "reversal_status",
        "rollback_executed",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"GovernanceRollbackRecord missing fields: {sorted(missing)}")

    if data["rollback_status"] not in ALLOWED_ROLLBACK_STATUSES:
        raise ValueError(f"Unsupported rollback_status: {data['rollback_status']}")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def _build_rollback_surfaces(current_status: str) -> Dict[str, str]:
    if current_status == PROMOTION_STATUS:
        return {
            "freeze": "freeze_candidate",
            "finalization": "finalization_candidate",
            "replay_audit": "audit_replay_valid_candidate",
            "authority_registry": "authority_valid_candidate",
            "quorum": "quorum_valid_candidate",
            "epoch": "epoch_valid_candidate",
            "rotation": "rotation_valid_candidate",
            "mutation_boundary": "mutation_forbidden_candidate",
            "rollback_authority": "rollback_requires_manual_authority",
        }

    return {
        "freeze": "not_applicable",
        "finalization": "not_applicable",
        "replay_audit": "not_applicable",
        "authority_registry": "not_applicable",
        "quorum": "not_applicable",
        "epoch": "not_applicable",
        "rotation": "not_applicable",
        "mutation_boundary": "mutation_forbidden",
        "rollback_authority": "rollback_not_applicable",
    }


def build_governance_rollback(
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    if evidence_id:
        template_paths = [DEFAULT_TEMPLATE_DIR / f"{evidence_id}.template.json"]
    else:
        template_paths = sorted(DEFAULT_TEMPLATE_DIR.glob("*.template.json"))

    records: List[GovernanceRollbackRecord] = []

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
            rollback_status = "rollback_candidate"
            reversal_status = f"{current_status}->{SAFE_STATUS}"
        elif current_status == SAFE_STATUS:
            target_status = SAFE_STATUS
            rollback_status = "rollback_not_needed"
            reversal_status = f"{current_status}->{current_status}"
        else:
            target_status = current_status
            rollback_status = "rollback_blocked"
            reversal_status = f"{current_status}->{current_status}"

        surfaces = _build_rollback_surfaces(current_status)

        rollback_material = json.dumps(
            {
                "evidence_id": record_evidence_id,
                "current_status": current_status,
                "target_status": target_status,
                "rollback_status": rollback_status,
                "reversal_status": reversal_status,
                "rollback_executed": False,
                "rollback_surfaces": surfaces,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

        rollback_hash = _sha256_text(rollback_material)

        record = GovernanceRollbackRecord(
            rollback_id=f"GOV_ROLLBACK_{record_evidence_id}_{rollback_hash[:16]}",
            evidence_id=record_evidence_id,
            rollback_status=rollback_status,
            rollback_surfaces=surfaces,
            rollback_hash=rollback_hash,
            current_status=current_status,
            target_status=target_status,
            reversal_status=reversal_status,
            rollback_executed=False,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes=(
                "Candidate-only governance rollback record. Rollback is admissibility "
                "evidence only and was not executed. No evidence approval, readiness "
                "escalation, public release, institutional release, quote generation, "
                "transcript generation, or report publication occurred."
            ),
        )

        validate_record(record)
        records.append(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    rollback_root = (
        _sha256_text("|".join(record.rollback_hash for record in records))
        if records
        else "0" * 64
    )

    summary = {
        "rollback_record_count": len(records),
        "rollback_candidate_count": sum(
            1 for record in records if record.rollback_status == "rollback_candidate"
        ),
        "rollback_not_needed_count": sum(
            1 for record in records if record.rollback_status == "rollback_not_needed"
        ),
        "rollback_blocked_count": sum(
            1 for record in records if record.rollback_status == "rollback_blocked"
        ),
        "rollback_invalid_count": sum(
            1 for record in records if record.rollback_status == "rollback_invalid"
        ),
        "rollback_root": rollback_root,
        "rollback_executed": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}