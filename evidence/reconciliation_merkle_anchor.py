#!/usr/bin/env python3
"""
Reconciliation Merkle Anchor Engine v1.

Builds deterministic Merkle-style batch commitments over reconciliation
hash-chain candidate records.

This lane does not approve evidence, mutate templates, execute rollback,
publish reports, or mark anything public/institutional/report ready.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_TEMPLATE_DIR = Path("data/real_evidence_inputs")
DEFAULT_OUTPUT_DIR = Path("outputs/reconciliation_merkle_anchor")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "reconciliation_merkle_anchor_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "reconciliation_merkle_anchor_summary.json"

PROMOTION_STATUS = "verified_for_approval_review"
SAFE_STATUS = "entered_pending_review"
GENESIS_HASH = "0" * 64

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_ANCHOR_STATUSES = {
    "anchor_candidate",
    "anchor_not_needed",
    "anchor_blocked",
}


@dataclass
class ReconciliationMerkleAnchorRecord:
    anchor_batch_id: str
    leaf_index: int
    evidence_id: str
    template_path: str
    current_status: str
    target_status: str
    leaf_hash: str
    merkle_root: str
    inclusion_proof: List[str]
    anchor_status: str
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


def _pair_hash(left: str, right: str) -> str:
    return _sha256_text(f"{left}|{right}")


def _merkle_root(leaves: List[str]) -> str:
    if not leaves:
        return GENESIS_HASH

    level = list(leaves)

    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])

        level = [
            _pair_hash(level[i], level[i + 1])
            for i in range(0, len(level), 2)
        ]

    return level[0]


def _inclusion_proof(leaves: List[str], index: int) -> List[str]:
    if not leaves:
        return []

    proof: List[str] = []
    level = list(leaves)
    idx = index

    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])

        sibling_idx = idx ^ 1
        proof.append(level[sibling_idx])

        idx = idx // 2

        level = [
            _pair_hash(level[i], level[i + 1])
            for i in range(0, len(level), 2)
        ]

    return proof


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "anchor_batch_id",
        "leaf_index",
        "evidence_id",
        "template_path",
        "current_status",
        "target_status",
        "leaf_hash",
        "merkle_root",
        "inclusion_proof",
        "anchor_status",
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
        raise ValueError(f"ReconciliationMerkleAnchorRecord missing fields: {sorted(missing)}")

    if data["anchor_status"] not in ALLOWED_ANCHOR_STATUSES:
        raise ValueError(f"Unsupported anchor_status: {data['anchor_status']}")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def _leaf_material(
    evidence_id: str,
    template_path: str,
    current_status: str,
    target_status: str,
    mutation_summary: str,
    anchor_status: str,
) -> str:
    return "|".join(
        [
            evidence_id,
            template_path,
            current_status,
            target_status,
            mutation_summary,
            anchor_status,
        ]
    )


def build_merkle_anchor(
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    if evidence_id:
        template_paths = [DEFAULT_TEMPLATE_DIR / f"{evidence_id}.template.json"]
    else:
        template_paths = sorted(DEFAULT_TEMPLATE_DIR.glob("*.template.json"))

    pending_records: List[Dict[str, Any]] = []
    leaves: List[str] = []

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
            anchor_status = "anchor_candidate"
        elif current_status == SAFE_STATUS:
            target_status = SAFE_STATUS
            mutation_summary = f"{current_status}->{current_status}"
            anchor_status = "anchor_not_needed"
        else:
            target_status = current_status
            mutation_summary = f"{current_status}->{current_status}"
            anchor_status = "anchor_blocked"

        leaf_hash = _sha256_text(
            _leaf_material(
                evidence_id=record_evidence_id,
                template_path=str(template_path),
                current_status=current_status,
                target_status=target_status,
                mutation_summary=mutation_summary,
                anchor_status=anchor_status,
            )
        )

        pending_records.append(
            {
                "evidence_id": record_evidence_id,
                "template_path": str(template_path),
                "current_status": current_status,
                "target_status": target_status,
                "leaf_hash": leaf_hash,
                "anchor_status": anchor_status,
                "mutation_summary": mutation_summary,
            }
        )
        leaves.append(leaf_hash)

    merkle_root = _merkle_root(leaves)
    anchor_batch_id = f"RECON_MERKLE_{merkle_root[:16]}"

    records: List[ReconciliationMerkleAnchorRecord] = []

    for idx, pending in enumerate(pending_records):
        record = ReconciliationMerkleAnchorRecord(
            anchor_batch_id=anchor_batch_id,
            leaf_index=idx,
            evidence_id=pending["evidence_id"],
            template_path=pending["template_path"],
            current_status=pending["current_status"],
            target_status=pending["target_status"],
            leaf_hash=pending["leaf_hash"],
            merkle_root=merkle_root,
            inclusion_proof=_inclusion_proof(leaves, idx),
            anchor_status=pending["anchor_status"],
            mutation_summary=pending["mutation_summary"],
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes=(
                "Candidate-only reconciliation Merkle anchor record. "
                "No rollback execution, evidence approval, readiness escalation, "
                "quote generation, transcript generation, timestamp generation, "
                "report generation, or public anchoring occurred."
            ),
        )
        validate_record(record)
        records.append(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    summary = {
        "anchor_record_count": len(records),
        "anchor_candidate_count": sum(
            1 for record in records if record.anchor_status == "anchor_candidate"
        ),
        "anchor_not_needed_count": sum(
            1 for record in records if record.anchor_status == "anchor_not_needed"
        ),
        "anchor_blocked_count": sum(
            1 for record in records if record.anchor_status == "anchor_blocked"
        ),
        "anchor_batch_id": anchor_batch_id,
        "merkle_root": merkle_root,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}