#!/usr/bin/env python3
"""
Canonical Graph Mutation Engine v1.

Builds deterministic graph mutation candidates from sealed canonical evidence
snapshots. This lane prepares lawful replacement operations for legacy
EvidenceObject payloads that may still contain empty URLs.

It does not mutate the case graph, does not generate the final report, does not
approve evidence, and does not mark release readiness.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_SNAPSHOT_STATUS = Path(
    "outputs/evidence_snapshot_sealing/evidence_snapshot_sealing_status.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/canonical_graph_mutation")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "canonical_graph_mutation_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "canonical_graph_mutation_summary.json"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "mutation_applied",
)

ALLOWED_MUTATION_STATUSES = {
    "mutation_candidate",
    "mutation_blocked_missing_snapshot",
    "mutation_blocked_unsealed_snapshot",
    "mutation_blocked_invalid_url",
    "mutation_invalid",
}


@dataclass
class CanonicalGraphMutationRecord:
    mutation_id: str
    evidence_id: str
    case_id: str
    mutation_status: str
    target_path_hint: str
    replacement_evidence_object: Dict[str, Any]
    canonical_url: str
    canonical_source_type: str
    content_hash: str
    snapshot_material_hash: str
    mutation_hash: str
    mutation_applied: bool
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


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_nonempty_url(value: Any) -> bool:
    return isinstance(value, str) and value.strip().startswith(("http://", "https://"))


def _load_snapshot_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    payload = _load_json(path)
    records = payload.get("records", []) if isinstance(payload, dict) else []
    return records if isinstance(records, list) else []


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "mutation_id",
        "evidence_id",
        "case_id",
        "mutation_status",
        "target_path_hint",
        "replacement_evidence_object",
        "canonical_url",
        "canonical_source_type",
        "content_hash",
        "snapshot_material_hash",
        "mutation_hash",
        "mutation_applied",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"CanonicalGraphMutationRecord missing fields: {sorted(missing)}")

    if data["mutation_status"] not in ALLOWED_MUTATION_STATUSES:
        raise ValueError(f"Unsupported mutation_status: {data['mutation_status']}")

    replacement = data["replacement_evidence_object"]
    if not isinstance(replacement, dict):
        raise ValueError("replacement_evidence_object must be an object")

    if data["mutation_status"] == "mutation_candidate":
        if not _is_nonempty_url(data["canonical_url"]):
            raise ValueError("canonical_url must be a non-empty http(s) URL")
        if not _is_nonempty_url(replacement.get("url")):
            raise ValueError("replacement_evidence_object.url must be a non-empty http(s) URL")
        if not data["content_hash"]:
            raise ValueError("content_hash must be non-empty for mutation_candidate")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def _build_replacement_evidence_object(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    evidence_id = str(snapshot.get("evidence_id") or "UNKNOWN")
    case_id = str(snapshot.get("case_id") or "UNKNOWN")
    canonical_url = str(snapshot.get("canonical_url") or "")
    source_type = str(snapshot.get("canonical_source_type") or "unknown")
    content_hash = str(snapshot.get("content_hash") or "")
    snapshot_material_hash = str(snapshot.get("snapshot_material_hash") or "")

    return {
        "evidence_id": evidence_id,
        "case_id": case_id,
        "url": canonical_url,
        "source_type": source_type,
        "verification_status": "verified_for_approval_review",
        "content_hash": content_hash,
        "snapshot_material_hash": snapshot_material_hash,
        "snapshot_sealed": bool(snapshot.get("snapshot_sealed", False)),
        "approved_evidence": False,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
        "notes": (
            "Canonical graph replacement EvidenceObject candidate. This object is "
            "not approved, not public-ready, not institutional-ready, and not report-ready."
        ),
    }


def _build_record_from_snapshot(snapshot: Dict[str, Any]) -> CanonicalGraphMutationRecord:
    evidence_id = str(snapshot.get("evidence_id") or "UNKNOWN")
    case_id = str(snapshot.get("case_id") or "UNKNOWN")
    canonical_url = str(snapshot.get("canonical_url") or "")
    canonical_source_type = str(snapshot.get("canonical_source_type") or "unknown")
    content_hash = str(snapshot.get("content_hash") or "")
    snapshot_material_hash = str(snapshot.get("snapshot_material_hash") or "")

    snapshot_status = str(snapshot.get("seal_status") or "")
    snapshot_sealed = bool(snapshot.get("snapshot_sealed", False))

    if snapshot_status != "snapshot_seal_candidate":
        status = "mutation_blocked_missing_snapshot"
    elif not snapshot_sealed:
        status = "mutation_blocked_unsealed_snapshot"
    elif not _is_nonempty_url(canonical_url):
        status = "mutation_blocked_invalid_url"
    else:
        status = "mutation_candidate"

    replacement = _build_replacement_evidence_object(snapshot)

    material = json.dumps(
        {
            "evidence_id": evidence_id,
            "case_id": case_id,
            "mutation_status": status,
            "target_path_hint": f"case[{case_id}].evidence[{evidence_id}]",
            "replacement_evidence_object": replacement,
            "content_hash": content_hash,
            "snapshot_material_hash": snapshot_material_hash,
            "mutation_applied": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    mutation_hash = _sha256_text(material)

    record = CanonicalGraphMutationRecord(
        mutation_id=f"GRAPH_MUTATION_{evidence_id}_{mutation_hash[:16]}",
        evidence_id=evidence_id,
        case_id=case_id,
        mutation_status=status,
        target_path_hint=f"case[{case_id}].evidence[{evidence_id}]",
        replacement_evidence_object=replacement,
        canonical_url=canonical_url,
        canonical_source_type=canonical_source_type,
        content_hash=content_hash,
        snapshot_material_hash=snapshot_material_hash,
        mutation_hash=mutation_hash,
        mutation_applied=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Graph mutation candidate only. No divergence case graph mutation, final report "
            "generation, approval, publication, or institutional release occurred."
        ),
    )

    validate_record(record)
    return record


def build_canonical_graph_mutation(
    evidence_id: Optional[str] = None,
    snapshot_status_path: Path = DEFAULT_SNAPSHOT_STATUS,
) -> Dict[str, Any]:
    snapshot_records = _load_snapshot_records(snapshot_status_path)

    if evidence_id:
        snapshot_records = [
            record for record in snapshot_records
            if record.get("evidence_id") == evidence_id
        ]

    records: List[CanonicalGraphMutationRecord] = []

    if not snapshot_records:
        material = json.dumps(
            {
                "evidence_id": evidence_id or "ALL",
                "mutation_status": "mutation_blocked_missing_snapshot",
                "mutation_applied": False,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        mutation_hash = _sha256_text(material)

        record = CanonicalGraphMutationRecord(
            mutation_id=f"GRAPH_MUTATION_{evidence_id or 'ALL'}_{mutation_hash[:16]}",
            evidence_id=evidence_id or "ALL",
            case_id="UNKNOWN",
            mutation_status="mutation_blocked_missing_snapshot",
            target_path_hint="UNKNOWN",
            replacement_evidence_object={},
            canonical_url="",
            canonical_source_type="unknown",
            content_hash="",
            snapshot_material_hash="",
            mutation_hash=mutation_hash,
            mutation_applied=False,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes="Snapshot seal proof is missing; graph mutation cannot be proposed.",
        )
        validate_record(record)
        records.append(record)
    else:
        for snapshot in snapshot_records:
            records.append(_build_record_from_snapshot(snapshot))

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    mutation_root = (
        _sha256_text("|".join(record.mutation_hash for record in records))
        if records
        else "0" * 64
    )

    summary = {
        "mutation_record_count": len(records),
        "mutation_candidate_count": sum(
            1 for record in records if record.mutation_status == "mutation_candidate"
        ),
        "mutation_blocked_missing_snapshot_count": sum(
            1 for record in records if record.mutation_status == "mutation_blocked_missing_snapshot"
        ),
        "mutation_blocked_unsealed_snapshot_count": sum(
            1 for record in records if record.mutation_status == "mutation_blocked_unsealed_snapshot"
        ),
        "mutation_blocked_invalid_url_count": sum(
            1 for record in records if record.mutation_status == "mutation_blocked_invalid_url"
        ),
        "mutation_invalid_count": sum(
            1 for record in records if record.mutation_status == "mutation_invalid"
        ),
        "mutation_root": mutation_root,
        "mutation_applied": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}