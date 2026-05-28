#!/usr/bin/env python3
"""
Proof-Carrying Report Assembly Engine v1.

Builds a deterministic report admissibility manifest before final report
generation. This is a pre-collapse proof layer: it does not generate the final
report, approve evidence, publish, or mark readiness. It classifies whether the
case graph can lawfully proceed to report assembly.

Core invariant:
report generation is refused unless every case evidence node has a non-empty
URL and every unresolved evidence edge is represented in normalization proof.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_CASE_GRAPH = Path("outputs/cases/divergence_cases.json")
DEFAULT_NORMALIZATION_STATUS = Path(
    "outputs/case_graph_normalization/case_graph_normalization_status.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/proof_carrying_report_assembly")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "proof_carrying_report_assembly_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "proof_carrying_report_assembly_summary.json"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "report_generated",
    "assembly_applied",
)

ALLOWED_ASSEMBLY_STATUSES = {
    "assembly_ready_candidate",
    "assembly_refused_unresolved_evidence",
    "assembly_blocked_missing_case_graph",
    "assembly_blocked_missing_normalization_proof",
    "assembly_invalid",
}


@dataclass
class ProofCarryingReportAssemblyRecord:
    assembly_id: str
    case_id: str
    assembly_status: str
    unresolved_evidence_ids: List[str]
    unresolved_evidence_count: int
    normalization_candidate_count: int
    normalization_proof_present: bool
    report_generated: bool
    assembly_applied: bool
    assembly_hash: str
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


def _iter_case_records(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("cases"), list):
            return payload["cases"]
        if isinstance(payload.get("divergence_cases"), list):
            return payload["divergence_cases"]
        if isinstance(payload.get("records"), list):
            return payload["records"]
    if isinstance(payload, list):
        return payload
    return []


def _find_evidence_nodes(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            maybe_evidence_id = obj.get("evidence_id") or obj.get("id")
            has_evidence_shape = (
                isinstance(maybe_evidence_id, str)
                and maybe_evidence_id.startswith("VID_")
            ) or "url" in obj

            if has_evidence_shape:
                nodes.append(
                    {
                        "evidence_id": maybe_evidence_id or "UNKNOWN",
                        "url": obj.get("url", ""),
                        "verification_status": obj.get("verification_status", ""),
                        "source_type": obj.get("source_type", ""),
                    }
                )

            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(case)
    return nodes


def _load_normalization_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    payload = _load_json(path)
    records = payload.get("records", []) if isinstance(payload, dict) else []
    return records if isinstance(records, list) else []


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "assembly_id",
        "case_id",
        "assembly_status",
        "unresolved_evidence_ids",
        "unresolved_evidence_count",
        "normalization_candidate_count",
        "normalization_proof_present",
        "report_generated",
        "assembly_applied",
        "assembly_hash",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"ProofCarryingReportAssemblyRecord missing fields: {sorted(missing)}")

    if data["assembly_status"] not in ALLOWED_ASSEMBLY_STATUSES:
        raise ValueError(f"Unsupported assembly_status: {data['assembly_status']}")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")

    if data["unresolved_evidence_count"] != len(data["unresolved_evidence_ids"]):
        raise ValueError("unresolved_evidence_count must equal unresolved_evidence_ids length")


def _build_record(
    case_id: str,
    unresolved_evidence_ids: List[str],
    normalization_candidate_count: int,
    normalization_proof_present: bool,
    case_graph_present: bool,
) -> ProofCarryingReportAssemblyRecord:
    unique_unresolved = sorted(set(unresolved_evidence_ids))

    if not case_graph_present:
        assembly_status = "assembly_blocked_missing_case_graph"
    elif not normalization_proof_present:
        assembly_status = "assembly_blocked_missing_normalization_proof"
    elif unique_unresolved:
        assembly_status = "assembly_refused_unresolved_evidence"
    else:
        assembly_status = "assembly_ready_candidate"

    material = json.dumps(
        {
            "case_id": case_id,
            "assembly_status": assembly_status,
            "unresolved_evidence_ids": unique_unresolved,
            "normalization_candidate_count": normalization_candidate_count,
            "normalization_proof_present": normalization_proof_present,
            "report_generated": False,
            "assembly_applied": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    assembly_hash = _sha256_text(material)

    record = ProofCarryingReportAssemblyRecord(
        assembly_id=f"REPORT_ASSEMBLY_{case_id}_{assembly_hash[:16]}",
        case_id=case_id,
        assembly_status=assembly_status,
        unresolved_evidence_ids=unique_unresolved,
        unresolved_evidence_count=len(unique_unresolved),
        normalization_candidate_count=normalization_candidate_count,
        normalization_proof_present=normalization_proof_present,
        report_generated=False,
        assembly_applied=False,
        assembly_hash=assembly_hash,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Proof-carrying report assembly preflight. Report generation is refused "
            "unless the case graph is present, normalization proof is present, and no "
            "case evidence node has an unresolved URL. No report was generated."
        ),
    )

    validate_record(record)
    return record


def build_proof_carrying_report_assembly(
    case_id: Optional[str] = None,
    case_graph_path: Path = DEFAULT_CASE_GRAPH,
    normalization_status_path: Path = DEFAULT_NORMALIZATION_STATUS,
) -> Dict[str, Any]:
    case_graph_present = case_graph_path.exists()
    normalization_records = _load_normalization_records(normalization_status_path)
    normalization_proof_present = bool(normalization_records)
    normalization_candidate_count = sum(
        1
        for record in normalization_records
        if record.get("normalization_status") == "normalization_candidate"
    )

    records: List[ProofCarryingReportAssemblyRecord] = []

    if case_graph_present:
        graph_payload = _load_json(case_graph_path)
        case_records = _iter_case_records(graph_payload)
    else:
        case_records = []

    if case_id:
        case_records = [
            case for case in case_records
            if str(case.get("case_id") or case.get("id")) == case_id
        ]

    if not case_records:
        records.append(
            _build_record(
                case_id=case_id or "ALL_CASES",
                unresolved_evidence_ids=[],
                normalization_candidate_count=normalization_candidate_count,
                normalization_proof_present=normalization_proof_present,
                case_graph_present=case_graph_present,
            )
        )
    else:
        for case in case_records:
            current_case_id = str(case.get("case_id") or case.get("id") or "UNKNOWN")
            evidence_nodes = _find_evidence_nodes(case)

            unresolved = [
                str(node.get("evidence_id") or "UNKNOWN")
                for node in evidence_nodes
                if not _is_nonempty_url(node.get("url"))
            ]

            records.append(
                _build_record(
                    case_id=current_case_id,
                    unresolved_evidence_ids=unresolved,
                    normalization_candidate_count=normalization_candidate_count,
                    normalization_proof_present=normalization_proof_present,
                    case_graph_present=case_graph_present,
                )
            )

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    assembly_root = (
        _sha256_text("|".join(record.assembly_hash for record in records))
        if records
        else "0" * 64
    )

    summary = {
        "assembly_record_count": len(records),
        "assembly_ready_candidate_count": sum(
            1 for record in records if record.assembly_status == "assembly_ready_candidate"
        ),
        "assembly_refused_unresolved_evidence_count": sum(
            1 for record in records if record.assembly_status == "assembly_refused_unresolved_evidence"
        ),
        "assembly_blocked_missing_case_graph_count": sum(
            1 for record in records if record.assembly_status == "assembly_blocked_missing_case_graph"
        ),
        "assembly_blocked_missing_normalization_proof_count": sum(
            1 for record in records if record.assembly_status == "assembly_blocked_missing_normalization_proof"
        ),
        "assembly_invalid_count": sum(
            1 for record in records if record.assembly_status == "assembly_invalid"
        ),
        "unresolved_evidence_total": sum(record.unresolved_evidence_count for record in records),
        "normalization_candidate_count": normalization_candidate_count,
        "normalization_proof_present": normalization_proof_present,
        "assembly_root": assembly_root,
        "report_generated": False,
        "assembly_applied": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}