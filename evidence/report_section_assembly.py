"""
report_section_assembly.py - Deterministic report-section payload assembly.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import json

from evidence.case_evidence_linking import (
    DEFAULT_CASE_LINK_OUTPUT,
    link_case_evidence_fixture_only,
)
from evidence.evidence_schema import (
    ReportSection,
    save_json,
    validate_case_object,
    validate_report_section,
)


DEFAULT_REPORT_SECTION_OUTPUT = Path("outputs/report_sections/report_sections.json")

ASSEMBLY_STATUSES = {
    "assembly_candidate",
    "assembly_verified",
    "assembly_rejected",
    "assembly_unavailable",
}

ASSEMBLY_REQUIRED_STATUSES = {"assembly_candidate", "assembly_verified"}
REASON_REQUIRED_STATUSES = {"assembly_rejected", "assembly_unavailable"}
PROHIBITED_EVIDENCE_STATUSES = {"report_ready"}

SECTION_FIXTURES = {
    ("CASE_002", "CLAIM_JOBS_001", "VID_JOBS_001"): {
        "section_id": "SECTION_CASE_002_JOBS",
        "heading": "Jobs Creation Promise Evidence",
    },
    ("CASE_006", "CLAIM_HEALTH_001", "VID_HEALTH_001"): {
        "section_id": "SECTION_CASE_006_HEALTH",
        "heading": "Healthcare Emergency Evidence",
    },
}


@dataclass
class AssembledReportSection:
    section_id: str
    case_id: str
    claim_ids: List[str]
    evidence_ids: List[str]
    heading: str
    body: str
    raw_quotes: List[str]
    timestamp_refs: List[Dict[str, str]]
    assembly_status: str
    assembly_notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_dict(value: Any) -> Dict[str, Any]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    raise ValueError(f"Expected object or dict, got {type(value).__name__}")


def _require_nonempty_string(data: Dict[str, Any], field_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"AssembledReportSection.{field_name} must be a non-empty string"
        )


def _require_nonempty_string_list(data: Dict[str, Any], field_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, list) or not value:
        raise ValueError(
            f"AssembledReportSection.{field_name} must be a non-empty list"
        )
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"AssembledReportSection.{field_name} must contain non-empty strings"
            )


def _require_timestamp_refs(data: Dict[str, Any]) -> None:
    refs = data.get("timestamp_refs")
    if not isinstance(refs, list) or not refs:
        raise ValueError(
            "AssembledReportSection.timestamp_refs must be a non-empty list"
        )
    for ref in refs:
        if not isinstance(ref, dict):
            raise ValueError(
                "AssembledReportSection.timestamp_refs must contain objects"
            )
        for field_name in ("evidence_id", "timestamp_start", "timestamp_end"):
            value = ref.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    "AssembledReportSection.timestamp_refs entries must preserve "
                    f"{field_name}"
                )


def validate_assembled_report_section(section: Any) -> None:
    data = _as_dict(section)

    for field_name in ("section_id", "case_id", "heading", "body", "assembly_status"):
        _require_nonempty_string(data, field_name)

    _require_nonempty_string(data, "assembly_notes")
    _require_nonempty_string_list(data, "claim_ids")
    _require_nonempty_string_list(data, "evidence_ids")

    status = data["assembly_status"]
    if status not in ASSEMBLY_STATUSES:
        raise ValueError(
            f"AssembledReportSection.assembly_status is unsupported: {status}"
        )

    evidence_status = data.get("evidence_verification_status")
    if evidence_status in PROHIBITED_EVIDENCE_STATUSES or data.get("report_ready"):
        raise ValueError(
            "Report section assembly cannot mark evidence as report_ready"
        )

    if status in ASSEMBLY_REQUIRED_STATUSES:
        _require_nonempty_string_list(data, "raw_quotes")
        _require_timestamp_refs(data)

    if status in REASON_REQUIRED_STATUSES and not data["assembly_notes"].strip():
        raise ValueError(
            f"AssembledReportSection.{status} requires assembly_notes"
        )


def load_case_link_artifact(
    input_path: Path = DEFAULT_CASE_LINK_OUTPUT,
) -> Dict[str, Any]:
    if not input_path.exists():
        link_case_evidence_fixture_only(input_path)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(data.get("links"), list):
        raise ValueError("Case link artifact must contain links")
    if not isinstance(data.get("cases"), list):
        raise ValueError("Case link artifact must contain cases")
    if not isinstance(data.get("report_sections"), list):
        raise ValueError("Case link artifact must contain report_sections")
    return data


def validate_assembled_section_resolves(
    section: Any,
    case: Any,
) -> None:
    validate_assembled_report_section(section)
    case_data = _as_dict(case)
    validate_case_object(case_data)

    section_data = _as_dict(section)
    if section_data["case_id"] != case_data["case_id"]:
        raise ValueError(
            f"AssembledReportSection {section_data['section_id']} case_id does not "
            f"match {case_data['case_id']}"
        )

    evidence_ids = {
        _as_dict(evidence)["evidence_id"] for evidence in case_data["evidence"]
    }
    claim_ids = {_as_dict(claim)["claim_id"] for claim in case_data["claims"]}

    for claim_id in section_data["claim_ids"]:
        if claim_id not in claim_ids:
            raise ValueError(
                f"AssembledReportSection {section_data['section_id']} references "
                f"unknown claim_id: {claim_id}"
            )

    for evidence_id in section_data["evidence_ids"]:
        if evidence_id not in evidence_ids:
            raise ValueError(
                f"AssembledReportSection {section_data['section_id']} references "
                f"unknown evidence_id: {evidence_id}"
            )

    validate_report_section(
        ReportSection(
            section_id=section_data["section_id"],
            case_id=section_data["case_id"],
            heading=section_data["heading"],
            body=section_data["body"],
            evidence_ids=list(section_data["evidence_ids"]),
        )
    )


def _case_by_id(cases: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for case in cases:
        validate_case_object(case)
        result[case["case_id"]] = case
    return result


def section_from_link(link: Dict[str, Any]) -> AssembledReportSection:
    key = (link.get("case_id"), link.get("claim_id"), link.get("evidence_id"))
    fixture = SECTION_FIXTURES.get(key)
    if link.get("link_status") == "link_verified" and fixture:
        section = AssembledReportSection(
            section_id=fixture["section_id"],
            case_id=str(link["case_id"]),
            claim_ids=[str(link["claim_id"])],
            evidence_ids=[str(link["evidence_id"])],
            heading=fixture["heading"],
            body=(
                "TEST FIXTURE ONLY. Assembled report-section payload for "
                "validation. Not real public evidence and not report-ready."
            ),
            raw_quotes=[str(link["raw_quote"])],
            timestamp_refs=[
                {
                    "evidence_id": str(link["evidence_id"]),
                    "timestamp_start": str(link["timestamp_start"]),
                    "timestamp_end": str(link["timestamp_end"]),
                }
            ],
            assembly_status="assembly_verified",
            assembly_notes=(
                "TEST FIXTURE ONLY. Report Section Assembly v1 validation payload. "
                "Final report generation pending."
            ),
        )
    else:
        section = AssembledReportSection(
            section_id=f"UNAVAILABLE_{link.get('quote_id', 'UNKNOWN')}",
            case_id=str(link.get("case_id", "")),
            claim_ids=[str(link.get("claim_id", ""))],
            evidence_ids=[str(link.get("evidence_id", ""))],
            heading="Unavailable Fixture Report Section",
            body=(
                "TEST FIXTURE ONLY. No deterministic Report Section Assembly v1 "
                "mapping exists for this link."
            ),
            raw_quotes=[],
            timestamp_refs=[],
            assembly_status="assembly_unavailable",
            assembly_notes=(
                "TEST FIXTURE ONLY. Link was not verified for report-section "
                "assembly. Not real public evidence."
            ),
        )
    validate_assembled_report_section(section)
    return section


def assemble_sections_from_artifact(
    artifact: Dict[str, Any],
) -> List[AssembledReportSection]:
    cases = _case_by_id(artifact["cases"])
    sections = [section_from_link(link) for link in artifact["links"]]
    for section in sections:
        if section.assembly_status == "assembly_verified":
            validate_assembled_section_resolves(section, cases[section.case_id])
    return sections


def write_report_sections(
    sections: List[AssembledReportSection],
    output_path: Path = DEFAULT_REPORT_SECTION_OUTPUT,
) -> Dict[str, Any]:
    for section in sections:
        validate_assembled_report_section(section)

    output = {
        "metadata": {
            "generated_at_utc": utc_now_iso(),
            "mode": "fixtures-only",
            "fixture_notice": "TEST FIXTURES ONLY. Not real public evidence.",
            "report_ready": False,
            "total_sections": len(sections),
        },
        "sections": [section.to_dict() for section in sections],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(output, str(output_path))
    return output


def assemble_report_sections_fixture_only(
    output_path: Path = DEFAULT_REPORT_SECTION_OUTPUT,
) -> Dict[str, Any]:
    artifact = load_case_link_artifact()
    sections = assemble_sections_from_artifact(artifact)
    write_report_sections(sections, output_path)

    verified_sections = [
        section for section in sections if section.assembly_status == "assembly_verified"
    ]

    return {
        "processed": len(artifact["links"]),
        "sections_candidate": sum(
            1 for section in sections if section.assembly_status == "assembly_candidate"
        ),
        "sections_verified": len(verified_sections),
        "sections_rejected": sum(
            1 for section in sections if section.assembly_status == "assembly_rejected"
        ),
        "sections_unavailable": sum(
            1
            for section in sections
            if section.assembly_status == "assembly_unavailable"
        ),
        "cases_represented": len({section.case_id for section in verified_sections}),
        "evidence_ids_represented": len(
            {
                evidence_id
                for section in verified_sections
                for evidence_id in section.evidence_ids
            }
        ),
        "output_path": str(output_path),
        "sections": sections,
    }
