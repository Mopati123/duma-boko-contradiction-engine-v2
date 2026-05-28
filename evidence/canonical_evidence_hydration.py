#!/usr/bin/env python3
"""
Canonical Evidence Hydration Engine v1.

Builds candidate-only hydration records for unresolved evidence nodes.

This lane does not approve evidence, does not mark public/institutional/report
readiness, and does not mutate case files. It identifies canonical replacement
sources for evidence objects with missing/empty/placeholder URLs.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


DEFAULT_TEMPLATE_DIR = Path("data/real_evidence_inputs")
DEFAULT_OUTPUT_DIR = Path("outputs/canonical_evidence_hydration")

STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "canonical_evidence_hydration_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "canonical_evidence_hydration_summary.json"

FORBIDDEN_TRUE_FLAGS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
    "hydration_applied",
)

ALLOWED_HYDRATION_STATUSES = {
    "hydration_candidate",
    "hydration_not_needed",
    "hydration_blocked",
    "hydration_invalid",
}

CANONICAL_SOURCE_MAP = {
    "VID_JOBS_001": {
        "case_id": "CASE_002",
        "canonical_url": "https://www.udc.org.bw/",
        "canonical_source_type": "official_manifesto_source",
        "canonical_candidate_id": "RECOVERY_VID_JOBS_001_UDC_HOME",
        "hydration_reason": "Replace missing/unstable video evidence with selected official manifesto source.",
    },
    "VID_HEALTH_001": {
        "case_id": "CASE_006",
        "canonical_url": "https://www.aljazeera.com/news/2025/8/26/botswana-declares-public-health-emergency-over-medicine-shortage",
        "canonical_source_type": "secondary_corroboration",
        "canonical_candidate_id": "RECOVERY_VID_HEALTH_001_AL_JAZEERA",
        "hydration_reason": "Replace unavailable captions/video evidence with selected article fallback source.",
    },
}


@dataclass
class CanonicalEvidenceHydrationRecord:
    hydration_id: str
    evidence_id: str
    case_id: str
    hydration_status: str
    canonical_candidate_id: str
    canonical_url: str
    canonical_source_type: str
    hydration_reason: str
    hydration_hash: str
    hydration_applied: bool
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


def _is_nonempty_url(value: Any) -> bool:
    return isinstance(value, str) and value.strip().startswith(("http://", "https://"))


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "hydration_id",
        "evidence_id",
        "case_id",
        "hydration_status",
        "canonical_candidate_id",
        "canonical_url",
        "canonical_source_type",
        "hydration_reason",
        "hydration_hash",
        "hydration_applied",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"CanonicalEvidenceHydrationRecord missing fields: {sorted(missing)}")

    if data["hydration_status"] not in ALLOWED_HYDRATION_STATUSES:
        raise ValueError(f"Unsupported hydration_status: {data['hydration_status']}")

    if data["hydration_status"] == "hydration_candidate":
        if not _is_nonempty_url(data["canonical_url"]):
            raise ValueError("canonical_url must be a non-empty http(s) URL")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_canonical_evidence_hydration(
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    if evidence_id:
        candidate_ids = [evidence_id]
    else:
        candidate_ids = sorted(CANONICAL_SOURCE_MAP)

    records: List[CanonicalEvidenceHydrationRecord] = []

    for record_evidence_id in candidate_ids:
        source = CANONICAL_SOURCE_MAP.get(record_evidence_id)

        if not source:
            hydration_status = "hydration_blocked"
            case_id = "UNKNOWN"
            canonical_url = ""
            canonical_source_type = "unknown"
            canonical_candidate_id = "UNKNOWN"
            hydration_reason = "No canonical hydration source mapped for this evidence ID."
        else:
            template_path = DEFAULT_TEMPLATE_DIR / f"{record_evidence_id}.template.json"
            template_payload = _load_json(template_path) if template_path.exists() else {}

            existing_url = template_payload.get("url") or template_payload.get("source_url")
            hydration_status = (
                "hydration_not_needed"
                if _is_nonempty_url(existing_url) and existing_url == source["canonical_url"]
                else "hydration_candidate"
            )

            case_id = source["case_id"]
            canonical_url = source["canonical_url"]
            canonical_source_type = source["canonical_source_type"]
            canonical_candidate_id = source["canonical_candidate_id"]
            hydration_reason = source["hydration_reason"]

        hydration_material = json.dumps(
            {
                "evidence_id": record_evidence_id,
                "case_id": case_id,
                "hydration_status": hydration_status,
                "canonical_candidate_id": canonical_candidate_id,
                "canonical_url": canonical_url,
                "canonical_source_type": canonical_source_type,
                "hydration_reason": hydration_reason,
                "hydration_applied": False,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

        hydration_hash = _sha256_text(hydration_material)

        record = CanonicalEvidenceHydrationRecord(
            hydration_id=f"HYDRATE_{record_evidence_id}_{hydration_hash[:16]}",
            evidence_id=record_evidence_id,
            case_id=case_id,
            hydration_status=hydration_status,
            canonical_candidate_id=canonical_candidate_id,
            canonical_url=canonical_url,
            canonical_source_type=canonical_source_type,
            hydration_reason=hydration_reason,
            hydration_hash=hydration_hash,
            hydration_applied=False,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            requires_manual_review=True,
            notes=(
                "Candidate-only canonical evidence hydration record. No evidence object "
                "was mutated, approved, published, marked report-ready, or institutionally released."
            ),
        )

        validate_record(record)
        records.append(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    hydration_root = (
        _sha256_text("|".join(record.hydration_hash for record in records))
        if records
        else "0" * 64
    )

    summary = {
        "hydration_record_count": len(records),
        "hydration_candidate_count": sum(
            1 for record in records if record.hydration_status == "hydration_candidate"
        ),
        "hydration_not_needed_count": sum(
            1 for record in records if record.hydration_status == "hydration_not_needed"
        ),
        "hydration_blocked_count": sum(
            1 for record in records if record.hydration_status == "hydration_blocked"
        ),
        "hydration_invalid_count": sum(
            1 for record in records if record.hydration_status == "hydration_invalid"
        ),
        "hydration_root": hydration_root,
        "hydration_applied": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)

    return {"payload": payload, "summary": summary}