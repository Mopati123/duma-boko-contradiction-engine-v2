#!/usr/bin/env python3
"""
Governance Anchor Bundle Engine v1.

Builds an anchor-ready bundle from the canonical evidence chain and governance
runtime outputs.

This lane does not publish to a blockchain, does not approve evidence, does not
mark public/institutional/report readiness, and does not mutate the final report.
It only creates deterministic anchor-candidate records and a bundle root.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_OUTPUT_DIR = Path("outputs/governance_anchor_bundle")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_anchor_bundle_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "governance_anchor_bundle_summary.json"

CHAIN_SUMMARY_PATHS = {
    "url_closure": Path("outputs/canonical_evidence_url_closure/canonical_evidence_url_closure_summary.json"),
    "resolution": Path("outputs/canonical_evidence_resolution/canonical_evidence_resolution_summary.json"),
    "injection": Path("outputs/canonical_evidence_injection/canonical_evidence_injection_summary.json"),
    "snapshot": Path("outputs/evidence_snapshot_sealing/evidence_snapshot_sealing_summary.json"),
    "mutation": Path("outputs/canonical_graph_mutation/canonical_graph_mutation_summary.json"),
    "collapse": Path("outputs/final_report_collapse_engine/final_report_collapse_summary.json"),
    "governance_signatures": Path("outputs/governance_signatures/governance_signature_summary.json"),
}

ROOT_KEYS = {
    "url_closure": "closure_root",
    "resolution": "resolution_root",
    "injection": "injection_root",
    "snapshot": "snapshot_root",
    "mutation": "mutation_root",
    "collapse": "collapse_root",
    "governance_signatures": "signature_root",
}

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "anchor_published",
    "bundle_applied",
)

ALLOWED_BUNDLE_STATUSES = {
    "anchor_bundle_candidate",
    "anchor_bundle_blocked_missing_chain_root",
    "anchor_bundle_invalid",
}


@dataclass
class GovernanceAnchorBundleRecord:
    bundle_id: str
    bundle_status: str
    chain_roots: Dict[str, str]
    missing_roots: List[str]
    anchor_material_hash: str
    anchor_bundle_root: str
    anchor_published: bool
    bundle_applied: bool
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


def _derive_governance_signature_root(payload: Dict[str, Any]) -> Optional[str]:
    signature_count = payload.get("signature_record_count", 0)
    candidate_count = payload.get("signature_candidate_count", 0)
    blocked_count = payload.get("signature_blocked_count", 0)

    if not signature_count or not candidate_count or blocked_count != 0:
        return None

    material = {
        "root_type": "derived_governance_signature_root_v1",
        "signature_record_count": signature_count,
        "signature_candidate_count": candidate_count,
        "signature_not_needed_count": payload.get("signature_not_needed_count", 0),
        "signature_blocked_count": blocked_count,
        "approved_evidence": payload.get("approved_evidence"),
        "public_ready": payload.get("public_ready"),
        "institutional_ready": payload.get("institutional_ready"),
        "report_ready": payload.get("report_ready"),
    }

    return _sha256_text(json.dumps(material, sort_keys=True, separators=(",", ":")))


def _load_chain_root(name: str, path: Path) -> Optional[str]:
    if not path.exists():
        return None

    payload = _load_json(path)
    if not isinstance(payload, dict):
        return None

    root_key = ROOT_KEYS[name]
    value = payload.get(root_key)

    if _is_nonzero_hash(value):
        return value.strip()

    if name == "governance_signatures":
        return _derive_governance_signature_root(payload)

    return None


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "bundle_id",
        "bundle_status",
        "chain_roots",
        "missing_roots",
        "anchor_material_hash",
        "anchor_bundle_root",
        "anchor_published",
        "bundle_applied",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"GovernanceAnchorBundleRecord missing fields: {sorted(missing)}")

    if data["bundle_status"] not in ALLOWED_BUNDLE_STATUSES:
        raise ValueError(f"Unsupported bundle_status: {data['bundle_status']}")

    if data["bundle_status"] == "anchor_bundle_candidate":
        if data["missing_roots"]:
            raise ValueError("missing_roots must be empty for anchor_bundle_candidate")
        if not data["chain_roots"]:
            raise ValueError("chain_roots must be non-empty for anchor_bundle_candidate")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_governance_anchor_bundle() -> Dict[str, Any]:
    chain_roots: Dict[str, str] = {}
    missing_roots: List[str] = []

    for name, path in CHAIN_SUMMARY_PATHS.items():
        root = _load_chain_root(name, path)
        if root:
            chain_roots[name] = root
        else:
            missing_roots.append(name)

    if missing_roots:
        status = "anchor_bundle_blocked_missing_chain_root"
    else:
        status = "anchor_bundle_candidate"

    anchor_material = {
        "bundle_version": "governance_anchor_bundle_v1",
        "bundle_status": status,
        "chain_roots": chain_roots,
        "missing_roots": missing_roots,
        "anchor_published": False,
        "bundle_applied": False,
    }

    anchor_material_hash = _sha256_text(
        json.dumps(anchor_material, sort_keys=True, separators=(",", ":"))
    )

    anchor_bundle_root = _sha256_text(
        json.dumps(
            {
                "anchor_material_hash": anchor_material_hash,
                "chain_roots": chain_roots,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )

    record = GovernanceAnchorBundleRecord(
        bundle_id=f"GOVERNANCE_ANCHOR_BUNDLE_{anchor_bundle_root[:16]}",
        bundle_status=status,
        chain_roots=chain_roots,
        missing_roots=missing_roots,
        anchor_material_hash=anchor_material_hash,
        anchor_bundle_root=anchor_bundle_root,
        anchor_published=False,
        bundle_applied=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Anchor bundle candidate only. No blockchain publication, evidence approval, "
            "public release, institutional release, report generation, or readiness flag "
            "mutation occurred."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    summary = {
        "anchor_bundle_record_count": 1,
        "anchor_bundle_candidate_count": 1 if status == "anchor_bundle_candidate" else 0,
        "anchor_bundle_blocked_missing_chain_root_count": (
            1 if status == "anchor_bundle_blocked_missing_chain_root" else 0
        ),
        "anchor_bundle_invalid_count": 0,
        "chain_root_count": len(chain_roots),
        "missing_root_count": len(missing_roots),
        "missing_roots": missing_roots,
        "anchor_material_hash": anchor_material_hash,
        "anchor_bundle_root": anchor_bundle_root,
        "anchor_published": False,
        "bundle_applied": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}