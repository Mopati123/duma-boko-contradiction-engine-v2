#!/usr/bin/env python3
"""
Case Graph Normalization Engine v1.

Builds candidate-only records for normalizing unresolved EvidenceObject nodes
inside the generated divergence case graph.

This engine does not approve evidence, does not publish, does not mark report
readiness, and does not mutate the canonical case graph unless a future explicit
write/apply mode is added.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_CASE_GRAPH = Path("outputs/cases/divergence_cases.json")
DEFAULT_OUTPUT_DIR = Path("outputs/case_graph_normalization")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "case_graph_normalization_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "case_graph_normalization_summary.json"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "normalization_applied",
)

ALLOWED_NORMALIZATION_STATUSES = {
    "normalization_candidate",
    "normalization_not_needed",
    "normalization_blocked",
    "normalization_invalid",
}

CANONICAL_EVIDENCE_MAP = {
    "VID_JOBS_001": {
        "case_id": "CASE_002",
        "normalized_url": "https://www.udc.org.bw/",
        "source_type": "official_manifesto_source",
        "verification_status": "verified_for_approval_review",
        "normalization_reason": "Hydrate missing CASE_002 evidence URL from canonical official manifesto source.",
    },
    "VID_HEALTH_001": {
        "case_id": "CASE_006",
        "normalized_url": "https://www.aljazeera.com/news/2025/8/26/botswana-declares-public-health-emergency-over-medicine-shortage",
        "source_type": "secondary_corroboration",
        "verification_status": "verified_for_approval_review",
        "normalization_reason": "Hydrate missing CASE_006 evidence URL from selected health fallback article source.",
    },
}


@dataclass
class CaseGraphNormalizationRecord:
    normalization_id: str
    case_id: str
    evidence_id: str
    normalization_status: str
    original_url: str
    normalized_url: str
    source_type: str
    verification_status: str
    normalization_reason: str
    normalization_hash: str
    normalization_applied: bool
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


def _iter_evidence_nodes(payload: Any) -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []

    def walk(obj: Any, current_case_id: str = "UNKNOWN") -> None:
        if isinstance(obj, dict):
            case_id = str(obj.get("case_id") or obj.get("id") or current_case_id)

            if "evidence_id" in obj or "url" in obj:
                evidence_id = obj.get("evidence_id") or obj.get("id") or "UNKNOWN"
                if isinstance(evidence_id, str) and evidence_id.startswith("VID_"):
                    nodes.append(
                        {
                            "case_id": case_id,
                            "evidence_id": evidence_id,
                            "url": obj.get("url", ""),
                            "source_type": obj.get("source_type", ""),
                            "verification_status": obj.get("verification_status", ""),
                        }
                    )

            for value in obj.values():
                walk(value, case_id)

        elif isinstance(obj, list):
            for item in obj:
                walk(item, current_case_id)

    walk(payload)
    return nodes


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "normalization_id",
        "case_id",
        "evidence_id",
        "normalization_status",
        "original_url",
        "normalized_url",
        "source_type",
        "verification_status",
        "normalization_reason",
        "normalization_hash",
        "normalization_applied",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"CaseGraphNormalizationRecord missing fields: {sorted(missing)}")

    if data["normalization_status"] not in ALLOWED_NORMALIZATION_STATUSES:
        raise ValueError(f"Unsupported normalization_status: {data['normalization_status']}")

    if data["normalization_status"] == "normalization_candidate":
        if not _is_nonempty_url(data["normalized_url"]):
            raise ValueError("normalized_url must be a non-empty http(s) URL")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def _build_record(
    case_id: str,
    evidence_id: str,
    original_url: str,
    source_type: str,
    verification_status: str,
) -> CaseGraphNormalizationRecord:
    canonical = CANONICAL_EVIDENCE_MAP.get(evidence_id)

    if canonical is None:
        normalization_status = "normalization_blocked"
        normalized_url = ""
        normalized_source_type = source_type or "unknown"
        normalized_verification_status = verification_status or "unknown"
        normalization_reason = "No canonical evidence mapping exists for this evidence node."
    elif _is_nonempty_url(original_url):
        normalization_status = "normalization_not_needed"
        normalized_url = original_url
        normalized_source_type = source_type or canonical["source_type"]
        normalized_verification_status = verification_status or canonical["verification_status"]
        normalization_reason = "Evidence node already has a non-empty URL."
    else:
        normalization_status = "normalization_candidate"
        normalized_url = canonical["normalized_url"]
        normalized_source_type = canonical["source_type"]
        normalized_verification_status = canonical["verification_status"]
        normalization_reason = canonical["normalization_reason"]

    material = json.dumps(
        {
            "case_id": case_id,
            "evidence_id": evidence_id,
            "normalization_status": normalization_status,
            "original_url": original_url,
            "normalized_url": normalized_url,
            "source_type": normalized_source_type,
            "verification_status": normalized_verification_status,
            "normalization_applied": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    normalization_hash = _sha256_text(material)

    record = CaseGraphNormalizationRecord(
        normalization_id=f"CASE_GRAPH_NORM_{evidence_id}_{normalization_hash[:16]}",
        case_id=case_id,
        evidence_id=evidence_id,
        normalization_status=normalization_status,
        original_url=original_url or "",
        normalized_url=normalized_url,
        source_type=normalized_source_type,
        verification_status=normalized_verification_status,
        normalization_reason=normalization_reason,
        normalization_hash=normalization_hash,
        normalization_applied=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Candidate-only case graph normalization record. No case graph mutation, "
            "evidence approval, public release, institutional release, or report publication occurred."
        ),
    )

    validate_record(record)
    return record


def build_case_graph_normalization(
    evidence_id: Optional[str] = None,
    case_graph_path: Path = DEFAULT_CASE_GRAPH,
) -> Dict[str, Any]:
    records: List[CaseGraphNormalizationRecord] = []

    if case_graph_path.exists():
        case_graph = _load_json(case_graph_path)
        nodes = _iter_evidence_nodes(case_graph)
    else:
        nodes = []

    if evidence_id:
        nodes = [node for node in nodes if node["evidence_id"] == evidence_id]

    # If the generated graph is absent or does not expose evidence nodes in the
    # expected structure, emit deterministic canonical candidates from the map.
    if not nodes:
        ids = [evidence_id] if evidence_id else sorted(CANONICAL_EVIDENCE_MAP)
        for mapped_id in ids:
            canonical = CANONICAL_EVIDENCE_MAP.get(mapped_id)
            if canonical is None:
                records.append(
                    _build_record(
                        case_id="UNKNOWN",
                        evidence_id=mapped_id or "UNKNOWN",
                        original_url="",
                        source_type="unknown",
                        verification_status="unknown",
                    )
                )
                continue

            records.append(
                _build_record(
                    case_id=canonical["case_id"],
                    evidence_id=mapped_id,
                    original_url="",
                    source_type=canonical["source_type"],
                    verification_status=canonical["verification_status"],
                )
            )
    else:
        for node in nodes:
            records.append(
                _build_record(
                    case_id=node["case_id"],
                    evidence_id=node["evidence_id"],
                    original_url=node.get("url", ""),
                    source_type=node.get("source_type", ""),
                    verification_status=node.get("verification_status", ""),
                )
            )

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    normalization_root = (
        _sha256_text("|".join(record.normalization_hash for record in records))
        if records
        else "0" * 64
    )

    summary = {
        "normalization_record_count": len(records),
        "normalization_candidate_count": sum(
            1 for record in records if record.normalization_status == "normalization_candidate"
        ),
        "normalization_not_needed_count": sum(
            1 for record in records if record.normalization_status == "normalization_not_needed"
        ),
        "normalization_blocked_count": sum(
            1 for record in records if record.normalization_status == "normalization_blocked"
        ),
        "normalization_invalid_count": sum(
            1 for record in records if record.normalization_status == "normalization_invalid"
        ),
        "normalization_root": normalization_root,
        "normalization_applied": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}