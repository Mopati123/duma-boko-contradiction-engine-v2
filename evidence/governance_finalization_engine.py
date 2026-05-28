#!/usr/bin/env python3
"""
Governance Finalization Engine v1.

Builds candidate-only constitutional finalization records.

This engine aggregates governance legality surfaces into a finalization
candidate without approving evidence or setting readiness flags.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_TEMPLATE_DIR = Path("data/real_evidence_inputs")
DEFAULT_OUTPUT_DIR = Path("outputs/governance_finalization_engine")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_finalization_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_finalization_summary.json"

PROMOTION_STATUS = "verified_for_approval_review"
SAFE_STATUS = "entered_pending_review"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_FINALIZATION_STATUSES = {
    "finalization_candidate",
    "finalization_not_needed",
    "finalization_blocked",
    "finalization_invalid",
}


@dataclass
class GovernanceFinalizationRecord:
    finalization_id: str
    evidence_id: str
    constitutional_surfaces: Dict[str, str]
    surface_count: int
    valid_surface_count: int
    finalization_status: str
    finalization_hash: str
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
        "finalization_id",
        "evidence_id",
        "constitutional_surfaces",
        "surface_count",
        "valid_surface_count",
        "finalization_status",
        "finalization_hash",
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
        raise ValueError(f"GovernanceFinalizationRecord missing fields: {sorted(missing)}")

    if data["finalization_status"] not in ALLOWED_FINALIZATION_STATUSES:
        raise ValueError(f"Unsupported finalization_status: {data['finalization_status']}")

    if data["surface_count"] != len(data["constitutional_surfaces"]):
        raise ValueError("surface_count must equal constitutional_surfaces length")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def _build_surfaces(current_status: str) -> Dict[str, str]:
    if current_status == PROMOTION_STATUS:
        return {
            "authority_registry": "authority_valid_candidate",
            "quorum": "quorum_valid_candidate",
            "epoch": "epoch_valid_candidate",
            "rotation": "rotation_valid_candidate",
            "replay_audit": "audit_replay_valid_candidate",
            "signature": "signature_candidate",
            "reconciliation": "reconciliation_candidate",
            "merkle_anchor": "anchor_candidate",
        }

    return {
        "authority_registry": "not_applicable",
        "quorum": "not_applicable",
        "epoch": "not_applicable",
        "rotation": "not_applicable",
        "replay_audit": "not_applicable",
        "signature": "not_applicable",
        "reconciliation": "not_applicable",
        "merkle_anchor": "not_applicable",
    }


def build_governance_finalization(
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    if evidence_id:
        template_paths = [DEFAULT_TEMPLATE_DIR / f"{evidence_id}.template.json"]
    else:
        template_paths = sorted(DEFAULT_TEMPLATE_DIR.glob("*.template.json"))

    records: List[GovernanceFinalizationRecord] = []

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
            finalization_status = "finalization_candidate"
        elif current_status == SAFE_STATUS:
            target_status = SAFE_STATUS
            mutation_summary = f"{current_status}->{current_status}"
            finalization_status = "finalization_not_needed"
        else:
            target_status = current_status
            mutation_summary = f"{current_status}->{current_status}"
            finalization_status = "finalization_blocked"

        surfaces = _build_surfaces(current_status)
        valid_surface_count = sum(
            1
            for value in surfaces.values()
            if value.endswith("_candidate") or value == "reconciliation_candidate"
        )

        finalization_material = json.dumps(
            {
                "evidence_id": record_evidence_id,
                "current_status": current_status,
                "target_status": target_status,
                "mutation_summary": mutation_summary,
                "finalization_status": finalization_status,
                "constitutional_surfaces": surfaces,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

        finalization_hash = _sha256_text(finalization_material)

        record = GovernanceFinalizationRecord(
            finalization_id=f"GOV_FINAL_{record_evidence_id}_{finalization_hash[:16]}",
            evidence_id=record_evidence_id,
            constitutional_surfaces=surfaces,
            surface_count=len(surfaces),
            valid_surface_count=valid_surface_count,
            finalization_status=finalization_status,
            finalization_hash=finalization_hash,
            current_status=current_status,
            target_status=target_status,
            mutation_summary=mutation_summary,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes=(
                "Candidate-only governance finalization record. No evidence approval, "
                "readiness escalation, rollback execution, public release, institutional "
                "release, quote generation, transcript generation, or report publication occurred."
            ),
        )

        validate_record(record)
        records.append(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    finalization_root = (
        _sha256_text("|".join(record.finalization_hash for record in records))
        if records
        else "0" * 64
    )

    summary = {
        "finalization_record_count": len(records),
        "finalization_candidate_count": sum(
            1 for record in records if record.finalization_status == "finalization_candidate"
        ),
        "finalization_not_needed_count": sum(
            1 for record in records if record.finalization_status == "finalization_not_needed"
        ),
        "finalization_blocked_count": sum(
            1 for record in records if record.finalization_status == "finalization_blocked"
        ),
        "finalization_invalid_count": sum(
            1 for record in records if record.finalization_status == "finalization_invalid"
        ),
        "finalization_root": finalization_root,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}