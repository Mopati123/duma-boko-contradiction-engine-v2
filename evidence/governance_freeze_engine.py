#!/usr/bin/env python3
"""
Governance Freeze Engine v1.

Builds candidate-only immutable governance freeze records.

A freeze candidate declares a mutation-refusal boundary, but does not approve
evidence, publish reports, or set public/institutional/report readiness.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional, List
import hashlib
import json


DEFAULT_TEMPLATE_DIR = Path("data/real_evidence_inputs")
DEFAULT_OUTPUT_DIR = Path("outputs/governance_freeze_engine")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_freeze_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_freeze_summary.json"

PROMOTION_STATUS = "verified_for_approval_review"
SAFE_STATUS = "entered_pending_review"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "mutation_permitted",
)

ALLOWED_FREEZE_STATUSES = {
    "freeze_candidate",
    "freeze_not_needed",
    "freeze_blocked",
    "freeze_invalid",
}


@dataclass
class GovernanceFreezeRecord:
    freeze_id: str
    evidence_id: str
    freeze_status: str
    freeze_surfaces: Dict[str, str]
    freeze_hash: str
    current_status: str
    target_status: str
    mutation_summary: str
    mutation_permitted: bool
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
        "freeze_id",
        "evidence_id",
        "freeze_status",
        "freeze_surfaces",
        "freeze_hash",
        "current_status",
        "target_status",
        "mutation_summary",
        "mutation_permitted",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"GovernanceFreezeRecord missing fields: {sorted(missing)}")

    if data["freeze_status"] not in ALLOWED_FREEZE_STATUSES:
        raise ValueError(f"Unsupported freeze_status: {data['freeze_status']}")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def _build_freeze_surfaces(current_status: str) -> Dict[str, str]:
    if current_status == PROMOTION_STATUS:
        return {
            "finalization": "finalization_candidate",
            "replay_audit": "audit_replay_valid_candidate",
            "authority_registry": "authority_valid_candidate",
            "quorum": "quorum_valid_candidate",
            "epoch": "epoch_valid_candidate",
            "rotation": "rotation_valid_candidate",
            "signature": "signature_candidate",
            "reconciliation": "reconciliation_candidate",
            "merkle_anchor": "anchor_candidate",
            "mutation_boundary": "mutation_forbidden_candidate",
        }

    return {
        "finalization": "not_applicable",
        "replay_audit": "not_applicable",
        "authority_registry": "not_applicable",
        "quorum": "not_applicable",
        "epoch": "not_applicable",
        "rotation": "not_applicable",
        "signature": "not_applicable",
        "reconciliation": "not_applicable",
        "merkle_anchor": "not_applicable",
        "mutation_boundary": "mutation_forbidden",
    }


def build_governance_freeze(
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    if evidence_id:
        template_paths = [DEFAULT_TEMPLATE_DIR / f"{evidence_id}.template.json"]
    else:
        template_paths = sorted(DEFAULT_TEMPLATE_DIR.glob("*.template.json"))

    records: List[GovernanceFreezeRecord] = []

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
            freeze_status = "freeze_candidate"
        elif current_status == SAFE_STATUS:
            target_status = SAFE_STATUS
            mutation_summary = f"{current_status}->{current_status}"
            freeze_status = "freeze_not_needed"
        else:
            target_status = current_status
            mutation_summary = f"{current_status}->{current_status}"
            freeze_status = "freeze_blocked"

        surfaces = _build_freeze_surfaces(current_status)

        freeze_material = json.dumps(
            {
                "evidence_id": record_evidence_id,
                "current_status": current_status,
                "target_status": target_status,
                "mutation_summary": mutation_summary,
                "freeze_status": freeze_status,
                "mutation_permitted": False,
                "freeze_surfaces": surfaces,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

        freeze_hash = _sha256_text(freeze_material)

        record = GovernanceFreezeRecord(
            freeze_id=f"GOV_FREEZE_{record_evidence_id}_{freeze_hash[:16]}",
            evidence_id=record_evidence_id,
            freeze_status=freeze_status,
            freeze_surfaces=surfaces,
            freeze_hash=freeze_hash,
            current_status=current_status,
            target_status=target_status,
            mutation_summary=mutation_summary,
            mutation_permitted=False,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes=(
                "Candidate-only governance freeze record. Mutation is not permitted "
                "after this candidate boundary without rollback authority. No evidence "
                "approval, readiness escalation, rollback execution, public release, "
                "institutional release, quote generation, transcript generation, or "
                "report publication occurred."
            ),
        )

        validate_record(record)
        records.append(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    freeze_root = (
        _sha256_text("|".join(record.freeze_hash for record in records))
        if records
        else "0" * 64
    )

    summary = {
        "freeze_record_count": len(records),
        "freeze_candidate_count": sum(
            1 for record in records if record.freeze_status == "freeze_candidate"
        ),
        "freeze_not_needed_count": sum(
            1 for record in records if record.freeze_status == "freeze_not_needed"
        ),
        "freeze_blocked_count": sum(
            1 for record in records if record.freeze_status == "freeze_blocked"
        ),
        "freeze_invalid_count": sum(
            1 for record in records if record.freeze_status == "freeze_invalid"
        ),
        "freeze_root": freeze_root,
        "mutation_permitted": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}