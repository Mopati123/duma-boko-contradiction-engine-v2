#!/usr/bin/env python3
"""
Deterministic Replay Proof Engine v1.

Builds candidate-only replay proofs showing whether the same local inputs
produce stable governance proof materials.

This lane does not approve evidence, mutate templates, execute rollback,
publish reports, or mark anything public/institutional/report ready.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_TEMPLATE_DIR = Path("data/real_evidence_inputs")
DEFAULT_OUTPUT_DIR = Path("outputs/deterministic_replay_proof")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "deterministic_replay_proof_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "deterministic_replay_proof_summary.json"

PROMOTION_STATUS = "verified_for_approval_review"
SAFE_STATUS = "entered_pending_review"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

ALLOWED_REPLAY_STATUSES = {
    "replay_candidate",
    "replay_not_needed",
    "replay_blocked",
}


@dataclass
class DeterministicReplayProofRecord:
    replay_id: str
    evidence_id: str
    template_path: str
    current_status: str
    target_status: str
    replay_input_hash: str
    replay_output_hash: str
    replay_hash: str
    replay_match_status: str
    replay_input_manifest: Dict[str, Any]
    replay_output_manifest: Dict[str, Any]
    replay_divergence_detection: List[str]
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


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "replay_id",
        "evidence_id",
        "template_path",
        "current_status",
        "target_status",
        "replay_input_hash",
        "replay_output_hash",
        "replay_hash",
        "replay_match_status",
        "replay_input_manifest",
        "replay_output_manifest",
        "replay_divergence_detection",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"DeterministicReplayProofRecord missing fields: {sorted(missing)}")

    if data["replay_match_status"] not in ALLOWED_REPLAY_STATUSES:
        raise ValueError(f"Unsupported replay_match_status: {data['replay_match_status']}")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def _build_manifests(template_path: Path) -> Dict[str, Any]:
    payload = _load_json(template_path)

    evidence_id = payload.get(
        "evidence_id",
        template_path.stem.replace(".template", ""),
    )
    current_status = payload.get("verification_status", "unknown")

    if current_status == PROMOTION_STATUS:
        target_status = SAFE_STATUS
        replay_status = "replay_candidate"
        mutation_summary = f"{current_status}->{SAFE_STATUS}"
        divergence_detection: List[str] = []
    elif current_status == SAFE_STATUS:
        target_status = SAFE_STATUS
        replay_status = "replay_not_needed"
        mutation_summary = f"{current_status}->{current_status}"
        divergence_detection = []
    else:
        target_status = current_status
        replay_status = "replay_blocked"
        mutation_summary = f"{current_status}->{current_status}"
        divergence_detection = [
            f"Unsupported replay source status: {current_status}"
        ]

    input_manifest = {
        "engine": "DeterministicReplayProofEngine.v1",
        "evidence_id": evidence_id,
        "template_path": str(template_path),
        "current_status": current_status,
        "template_evidence_id": payload.get("evidence_id", ""),
        "template_case_id": payload.get("case_id", ""),
        "template_source_url": payload.get("source_url", ""),
    }

    output_manifest = {
        "target_status": target_status,
        "mutation_summary": mutation_summary,
        "replay_match_status": replay_status,
        "approved_evidence": False,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
        "requires_manual_review": True,
    }

    return {
        "evidence_id": evidence_id,
        "current_status": current_status,
        "target_status": target_status,
        "replay_status": replay_status,
        "input_manifest": input_manifest,
        "output_manifest": output_manifest,
        "divergence_detection": divergence_detection,
    }


def build_replay_proof(
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    if evidence_id:
        template_paths = [DEFAULT_TEMPLATE_DIR / f"{evidence_id}.template.json"]
    else:
        template_paths = sorted(DEFAULT_TEMPLATE_DIR.glob("*.template.json"))

    records: List[DeterministicReplayProofRecord] = []

    for template_path in template_paths:
        if not template_path.exists():
            continue

        manifests = _build_manifests(template_path)

        input_hash = _sha256_text(_canonical_json(manifests["input_manifest"]))
        output_hash = _sha256_text(_canonical_json(manifests["output_manifest"]))
        replay_hash = _sha256_text(f"{input_hash}|{output_hash}")

        record = DeterministicReplayProofRecord(
            replay_id=f"REPLAY_{replay_hash[:16]}",
            evidence_id=manifests["evidence_id"],
            template_path=str(template_path),
            current_status=manifests["current_status"],
            target_status=manifests["target_status"],
            replay_input_hash=input_hash,
            replay_output_hash=output_hash,
            replay_hash=replay_hash,
            replay_match_status=manifests["replay_status"],
            replay_input_manifest=manifests["input_manifest"],
            replay_output_manifest=manifests["output_manifest"],
            replay_divergence_detection=manifests["divergence_detection"],
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes=(
                "Candidate-only deterministic replay proof. "
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

    replay_root = _sha256_text(
        "|".join(record.replay_hash for record in records)
    ) if records else "0" * 64

    summary = {
        "replay_record_count": len(records),
        "replay_candidate_count": sum(
            1 for record in records if record.replay_match_status == "replay_candidate"
        ),
        "replay_not_needed_count": sum(
            1 for record in records if record.replay_match_status == "replay_not_needed"
        ),
        "replay_blocked_count": sum(
            1 for record in records if record.replay_match_status == "replay_blocked"
        ),
        "replay_root": replay_root,
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