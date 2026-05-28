#!/usr/bin/env python3
"""
Governance Replay Audit Engine v1.

Builds candidate-only replay audit records that reconstruct the deterministic
governance chronology for evidence-state transitions.

No evidence approval, readiness escalation, rollback execution,
public release, institutional release, or report publication occurs.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_TEMPLATE_DIR = Path("data/real_evidence_inputs")
DEFAULT_OUTPUT_DIR = Path("outputs/governance_replay_audit_engine")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_replay_audit_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_replay_audit_summary.json"

PROMOTION_STATUS = "verified_for_approval_review"
SAFE_STATUS = "entered_pending_review"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_AUDIT_STATUSES = {
    "audit_replay_valid_candidate",
    "audit_replay_not_needed",
    "audit_replay_blocked",
    "audit_replay_invalid",
}


@dataclass
class GovernanceReplayAuditRecord:
    audit_id: str
    evidence_id: str
    replay_sequence: List[Dict[str, Any]]
    replay_event_count: int
    audit_status: str
    audit_hash: str
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
        "audit_id",
        "evidence_id",
        "replay_sequence",
        "replay_event_count",
        "audit_status",
        "audit_hash",
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
        raise ValueError(f"GovernanceReplayAuditRecord missing fields: {sorted(missing)}")

    if data["audit_status"] not in ALLOWED_AUDIT_STATUSES:
        raise ValueError(f"Unsupported audit_status: {data['audit_status']}")

    if not isinstance(data["replay_sequence"], list):
        raise ValueError("replay_sequence must be a list")

    if data["replay_event_count"] != len(data["replay_sequence"]):
        raise ValueError("replay_event_count must equal replay_sequence length")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def _build_replay_sequence(evidence_id: str, current_status: str, target_status: str) -> List[Dict[str, Any]]:
    return [
        {
            "event_order": 1,
            "event_name": "candidate_template_observed",
            "event_status": current_status,
        },
        {
            "event_order": 2,
            "event_name": "governance_signature_candidate",
            "event_status": "signature_candidate" if current_status == PROMOTION_STATUS else "signature_not_applicable",
        },
        {
            "event_order": 3,
            "event_name": "governance_authority_checked",
            "event_status": "authority_valid_candidate" if current_status == PROMOTION_STATUS else "authority_not_applicable",
        },
        {
            "event_order": 4,
            "event_name": "governance_quorum_checked",
            "event_status": "quorum_valid_candidate" if current_status == PROMOTION_STATUS else "quorum_not_applicable",
        },
        {
            "event_order": 5,
            "event_name": "governance_epoch_checked",
            "event_status": "epoch_valid_candidate" if current_status == PROMOTION_STATUS else "epoch_not_applicable",
        },
        {
            "event_order": 6,
            "event_name": "governance_rotation_checked",
            "event_status": "rotation_valid_candidate" if current_status == PROMOTION_STATUS else "rotation_not_applicable",
        },
        {
            "event_order": 7,
            "event_name": "safe_target_status_declared",
            "event_status": target_status,
        },
    ]


def build_governance_replay_audit(
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    if evidence_id:
        template_paths = [DEFAULT_TEMPLATE_DIR / f"{evidence_id}.template.json"]
    else:
        template_paths = sorted(DEFAULT_TEMPLATE_DIR.glob("*.template.json"))

    records: List[GovernanceReplayAuditRecord] = []

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
            audit_status = "audit_replay_valid_candidate"
        elif current_status == SAFE_STATUS:
            target_status = SAFE_STATUS
            mutation_summary = f"{current_status}->{current_status}"
            audit_status = "audit_replay_not_needed"
        else:
            target_status = current_status
            mutation_summary = f"{current_status}->{current_status}"
            audit_status = "audit_replay_blocked"

        replay_sequence = _build_replay_sequence(
            evidence_id=record_evidence_id,
            current_status=current_status,
            target_status=target_status,
        )

        audit_material = json.dumps(
            {
                "evidence_id": record_evidence_id,
                "current_status": current_status,
                "target_status": target_status,
                "mutation_summary": mutation_summary,
                "audit_status": audit_status,
                "replay_sequence": replay_sequence,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

        audit_hash = _sha256_text(audit_material)

        record = GovernanceReplayAuditRecord(
            audit_id=f"GOV_AUDIT_{record_evidence_id}_{audit_hash[:16]}",
            evidence_id=record_evidence_id,
            replay_sequence=replay_sequence,
            replay_event_count=len(replay_sequence),
            audit_status=audit_status,
            audit_hash=audit_hash,
            current_status=current_status,
            target_status=target_status,
            mutation_summary=mutation_summary,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes=(
                "Candidate-only governance replay audit record. No evidence approval, "
                "readiness escalation, rollback execution, public release, "
                "institutional release, quote generation, transcript generation, "
                "or report publication occurred."
            ),
        )

        validate_record(record)
        records.append(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    audit_root = (
        _sha256_text("|".join(record.audit_hash for record in records))
        if records
        else "0" * 64
    )

    summary = {
        "audit_record_count": len(records),
        "audit_replay_valid_candidate_count": sum(
            1 for record in records if record.audit_status == "audit_replay_valid_candidate"
        ),
        "audit_replay_not_needed_count": sum(
            1 for record in records if record.audit_status == "audit_replay_not_needed"
        ),
        "audit_replay_blocked_count": sum(
            1 for record in records if record.audit_status == "audit_replay_blocked"
        ),
        "audit_replay_invalid_count": sum(
            1 for record in records if record.audit_status == "audit_replay_invalid"
        ),
        "audit_root": audit_root,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}