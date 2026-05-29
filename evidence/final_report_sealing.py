#!/usr/bin/env python3
"""
Final Report Sealing Engine v1.

Builds deterministic final report seal candidates from governance anchor bundle
outputs. This is an institutional packet preflight layer.

It does not generate a report, publish an anchor, approve evidence, or mark any
public/institutional/report readiness flag.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_ANCHOR_BUNDLE_STATUS = Path(
    "outputs/governance_anchor_bundle/governance_anchor_bundle_status.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/final_report_sealing")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "final_report_sealing_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "final_report_sealing_summary.json"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "seal_applied",
    "report_generated",
    "anchor_published",
)

ALLOWED_SEAL_STATUSES = {
    "final_report_seal_candidate",
    "final_report_seal_blocked_missing_anchor_bundle",
    "final_report_seal_blocked_invalid_anchor_bundle",
    "final_report_seal_invalid",
}


@dataclass
class FinalReportSealRecord:
    seal_id: str
    seal_status: str
    anchor_bundle_root: str
    anchor_material_hash: str
    institutional_packet_hash: str
    final_report_seal_root: str
    chain_roots: Dict[str, str]
    missing_roots: List[str]
    seal_applied: bool
    report_generated: bool
    anchor_published: bool
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


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _load_anchor_bundle_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    payload = _load_json(path)
    records = payload.get("records", []) if isinstance(payload, dict) else []
    return records if isinstance(records, list) else []


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "seal_id",
        "seal_status",
        "anchor_bundle_root",
        "anchor_material_hash",
        "institutional_packet_hash",
        "final_report_seal_root",
        "chain_roots",
        "missing_roots",
        "seal_applied",
        "report_generated",
        "anchor_published",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"FinalReportSealRecord missing fields: {sorted(missing)}")

    if data["seal_status"] not in ALLOWED_SEAL_STATUSES:
        raise ValueError(f"Unsupported seal_status: {data['seal_status']}")

    if data["seal_status"] == "final_report_seal_candidate":
        if not _is_nonzero_hash(data["anchor_bundle_root"]):
            raise ValueError("anchor_bundle_root must be a non-zero hash")
        if not _is_nonzero_hash(data["anchor_material_hash"]):
            raise ValueError("anchor_material_hash must be a non-zero hash")
        if data["missing_roots"]:
            raise ValueError("missing_roots must be empty for final_report_seal_candidate")
        if not data["chain_roots"]:
            raise ValueError("chain_roots must be non-empty for final_report_seal_candidate")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def _build_record_from_anchor(anchor: Dict[str, Any]) -> FinalReportSealRecord:
    anchor_bundle_root = str(anchor.get("anchor_bundle_root") or "")
    anchor_material_hash = str(anchor.get("anchor_material_hash") or "")
    chain_roots = anchor.get("chain_roots") or {}
    missing_roots = anchor.get("missing_roots") or []

    if (
        anchor.get("bundle_status") != "anchor_bundle_candidate"
        or not _is_nonzero_hash(anchor_bundle_root)
        or not _is_nonzero_hash(anchor_material_hash)
        or missing_roots
        or not isinstance(chain_roots, dict)
        or not chain_roots
    ):
        status = "final_report_seal_blocked_invalid_anchor_bundle"
    else:
        status = "final_report_seal_candidate"

    institutional_packet_material = {
        "packet_version": "final_report_institutional_packet_v1",
        "seal_status": status,
        "anchor_bundle_root": anchor_bundle_root,
        "anchor_material_hash": anchor_material_hash,
        "chain_roots": chain_roots,
        "missing_roots": missing_roots,
        "seal_applied": False,
        "report_generated": False,
        "anchor_published": False,
        "approved_evidence": False,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    institutional_packet_hash = _sha256_text(
        json.dumps(institutional_packet_material, sort_keys=True, separators=(",", ":"))
    )

    final_report_seal_root = _sha256_text(
        json.dumps(
            {
                "institutional_packet_hash": institutional_packet_hash,
                "anchor_bundle_root": anchor_bundle_root,
                "anchor_material_hash": anchor_material_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )

    record = FinalReportSealRecord(
        seal_id=f"FINAL_REPORT_SEAL_{final_report_seal_root[:16]}",
        seal_status=status,
        anchor_bundle_root=anchor_bundle_root,
        anchor_material_hash=anchor_material_hash,
        institutional_packet_hash=institutional_packet_hash,
        final_report_seal_root=final_report_seal_root,
        chain_roots=chain_roots if isinstance(chain_roots, dict) else {},
        missing_roots=missing_roots if isinstance(missing_roots, list) else ["invalid_missing_roots"],
        seal_applied=False,
        report_generated=False,
        anchor_published=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Final report seal candidate only. No report generation, evidence approval, "
            "anchor publication, public release, institutional release, or readiness "
            "flag mutation occurred."
        ),
    )

    validate_record(record)
    return record


def build_final_report_sealing(
    anchor_bundle_status_path: Path = DEFAULT_ANCHOR_BUNDLE_STATUS,
) -> Dict[str, Any]:
    anchor_records = _load_anchor_bundle_records(anchor_bundle_status_path)

    records: List[FinalReportSealRecord] = []

    if not anchor_records:
        material = json.dumps(
            {
                "seal_status": "final_report_seal_blocked_missing_anchor_bundle",
                "seal_applied": False,
                "report_generated": False,
                "anchor_published": False,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

        final_report_seal_root = _sha256_text(material)

        record = FinalReportSealRecord(
            seal_id=f"FINAL_REPORT_SEAL_{final_report_seal_root[:16]}",
            seal_status="final_report_seal_blocked_missing_anchor_bundle",
            anchor_bundle_root="",
            anchor_material_hash="",
            institutional_packet_hash=final_report_seal_root,
            final_report_seal_root=final_report_seal_root,
            chain_roots={},
            missing_roots=["governance_anchor_bundle"],
            seal_applied=False,
            report_generated=False,
            anchor_published=False,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes="Governance anchor bundle is missing; final report seal cannot proceed.",
        )
        validate_record(record)
        records.append(record)
    else:
        for anchor in anchor_records:
            records.append(_build_record_from_anchor(anchor))

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    final_report_seal_root = (
        _sha256_text("|".join(record.final_report_seal_root for record in records))
        if records
        else "0" * 64
    )

    summary = {
        "final_report_seal_record_count": len(records),
        "final_report_seal_candidate_count": sum(
            1 for record in records if record.seal_status == "final_report_seal_candidate"
        ),
        "final_report_seal_blocked_missing_anchor_bundle_count": sum(
            1 for record in records
            if record.seal_status == "final_report_seal_blocked_missing_anchor_bundle"
        ),
        "final_report_seal_blocked_invalid_anchor_bundle_count": sum(
            1 for record in records
            if record.seal_status == "final_report_seal_blocked_invalid_anchor_bundle"
        ),
        "final_report_seal_invalid_count": sum(
            1 for record in records if record.seal_status == "final_report_seal_invalid"
        ),
        "final_report_seal_root": final_report_seal_root,
        "seal_applied": False,
        "report_generated": False,
        "anchor_published": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}