#!/usr/bin/env python3
"""
Governance Quorum Engine v1.

Builds candidate-only N-of-M quorum validation records.

No evidence approval, readiness escalation, rollback execution,
public release, institutional release, or report publication occurs.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_TEMPLATE_DIR = Path("data/real_evidence_inputs")
DEFAULT_OUTPUT_DIR = Path("outputs/governance_quorum_engine")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_quorum_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_quorum_summary.json"

PROMOTION_STATUS = "verified_for_approval_review"
SAFE_STATUS = "entered_pending_review"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_QUORUM_STATUSES = {
    "quorum_valid_candidate",
    "quorum_not_needed",
    "quorum_blocked",
    "quorum_invalid",
}


@dataclass
class GovernanceQuorumRecord:
    quorum_id: str
    evidence_id: str
    required_authority_count: int
    observed_authority_count: int
    quorum_threshold: str
    quorum_status: str
    authority_votes: List[Dict[str, Any]]
    quorum_hash: str
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
        "quorum_id",
        "evidence_id",
        "required_authority_count",
        "observed_authority_count",
        "quorum_threshold",
        "quorum_status",
        "authority_votes",
        "quorum_hash",
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
        raise ValueError(f"GovernanceQuorumRecord missing fields: {sorted(missing)}")

    if data["quorum_status"] not in ALLOWED_QUORUM_STATUSES:
        raise ValueError(f"Unsupported quorum_status: {data['quorum_status']}")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def _authority_votes(evidence_id: str, current_status: str) -> List[Dict[str, Any]]:
    vote_status = "valid_candidate" if current_status == PROMOTION_STATUS else "not_applicable"

    return [
        {
            "authority_id": "AUTH_CANDIDATE_MANUAL_REVIEWER",
            "authority_role": "manual_review",
            "vote_status": vote_status,
        },
        {
            "authority_id": "AUTH_CANDIDATE_GOVERNANCE_REVIEWER",
            "authority_role": "governance_review",
            "vote_status": vote_status,
        },
    ]


def build_governance_quorum(
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    if evidence_id:
        template_paths = [DEFAULT_TEMPLATE_DIR / f"{evidence_id}.template.json"]
    else:
        template_paths = sorted(DEFAULT_TEMPLATE_DIR.glob("*.template.json"))

    records: List[GovernanceQuorumRecord] = []

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
            quorum_status = "quorum_valid_candidate"
        elif current_status == SAFE_STATUS:
            target_status = SAFE_STATUS
            mutation_summary = f"{current_status}->{current_status}"
            quorum_status = "quorum_not_needed"
        else:
            target_status = current_status
            mutation_summary = f"{current_status}->{current_status}"
            quorum_status = "quorum_blocked"

        votes = _authority_votes(record_evidence_id, current_status)
        required_authority_count = 2
        observed_authority_count = sum(
            1 for vote in votes if vote["vote_status"] == "valid_candidate"
        )

        if current_status == PROMOTION_STATUS and observed_authority_count < required_authority_count:
            quorum_status = "quorum_invalid"

        quorum_material = json.dumps(
            {
                "evidence_id": record_evidence_id,
                "current_status": current_status,
                "target_status": target_status,
                "mutation_summary": mutation_summary,
                "votes": votes,
                "required_authority_count": required_authority_count,
                "observed_authority_count": observed_authority_count,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

        quorum_hash = _sha256_text(quorum_material)

        record = GovernanceQuorumRecord(
            quorum_id=f"QUORUM_{record_evidence_id}_{quorum_hash[:16]}",
            evidence_id=record_evidence_id,
            required_authority_count=required_authority_count,
            observed_authority_count=observed_authority_count,
            quorum_threshold="2-of-2",
            quorum_status=quorum_status,
            authority_votes=votes,
            quorum_hash=quorum_hash,
            current_status=current_status,
            target_status=target_status,
            mutation_summary=mutation_summary,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes=(
                "Candidate-only governance quorum record. No approval, readiness "
                "escalation, rollback execution, public release, institutional "
                "release, quote generation, transcript generation, or report "
                "publication occurred."
            ),
        )

        validate_record(record)
        records.append(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    summary = {
        "quorum_record_count": len(records),
        "quorum_valid_candidate_count": sum(
            1 for record in records if record.quorum_status == "quorum_valid_candidate"
        ),
        "quorum_not_needed_count": sum(
            1 for record in records if record.quorum_status == "quorum_not_needed"
        ),
        "quorum_blocked_count": sum(
            1 for record in records if record.quorum_status == "quorum_blocked"
        ),
        "quorum_invalid_count": sum(
            1 for record in records if record.quorum_status == "quorum_invalid"
        ),
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}