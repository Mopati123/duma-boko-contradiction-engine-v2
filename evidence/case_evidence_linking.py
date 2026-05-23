"""
case_evidence_linking.py - Deterministic case/evidence link validation.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
import json
import re

from evidence.evidence_loader import load_seed_evidence
from evidence.evidence_schema import (
    CaseObject,
    ClaimObject,
    EvidenceObject,
    ReportSection,
    save_json,
    validate_case_object,
    validate_claim_object,
    validate_evidence_object,
    validate_report_section,
)
from evidence.quote_verification import (
    DEFAULT_QUOTE_OUTPUT,
    QuoteCandidate,
    validate_quote_candidate,
    verify_quotes_fixture_only,
)


DEFAULT_CASE_LINK_OUTPUT = Path("outputs/case_links/case_evidence_links.json")

LINK_STATUSES = {
    "link_candidate",
    "link_verified",
    "link_rejected",
    "link_unavailable",
}

REASON_REQUIRED_STATUSES = {"link_rejected", "link_unavailable"}
PROHIBITED_EVIDENCE_STATUSES = {"report_ready"}

FIXTURE_LINK_TARGETS = {
    ("VID_JOBS_001", "500 000 new jobs"): {
        "case_id": "CASE_002",
        "claim_id": "CLAIM_JOBS_001",
        "claim_type": "promise_quote_fixture",
        "claim_text": (
            "TEST FIXTURE ONLY. Draft claim linked to jobs promise quote evidence."
        ),
        "title": "Jobs creation quote evidence link fixture",
        "domain": "jobs_creation",
        "divergence_type": "promise_delivery_divergence",
    },
    ("VID_HEALTH_001", "public health emergency"): {
        "case_id": "CASE_006",
        "claim_id": "CLAIM_HEALTH_001",
        "claim_type": "outcome_quote_fixture",
        "claim_text": (
            "TEST FIXTURE ONLY. Draft claim linked to healthcare outcome quote evidence."
        ),
        "title": "Healthcare emergency quote evidence link fixture",
        "domain": "healthcare_reform",
        "divergence_type": "promise_delivery_divergence",
    },
}


@dataclass
class CaseEvidenceLink:
    case_id: str
    claim_id: str
    evidence_id: str
    quote_id: str
    phrase: str
    timestamp_start: str
    timestamp_end: str
    raw_quote: str
    link_status: str
    link_notes: str

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


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_").upper()
    return slug or "UNKNOWN"


def quote_id_for(evidence_id: str, raw_quote: str) -> str:
    return f"QUOTE_{evidence_id}_{slugify(raw_quote)}"


def validate_case_evidence_link(link: Any) -> None:
    data = _as_dict(link)
    for field_name in (
        "case_id",
        "claim_id",
        "evidence_id",
        "quote_id",
        "phrase",
        "timestamp_start",
        "timestamp_end",
        "raw_quote",
        "link_status",
        "link_notes",
    ):
        value = data.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"CaseEvidenceLink.{field_name} must be a non-empty string")

    if data["link_status"] not in LINK_STATUSES:
        raise ValueError(f"CaseEvidenceLink.link_status is unsupported: {data['link_status']}")

    evidence_status = data.get("evidence_verification_status")
    if evidence_status in PROHIBITED_EVIDENCE_STATUSES or data.get("report_ready"):
        raise ValueError("Case evidence links cannot mark evidence as report_ready")

    if data["link_status"] in REASON_REQUIRED_STATUSES and not data["link_notes"].strip():
        raise ValueError(
            f"CaseEvidenceLink.{data['link_status']} requires link_notes"
        )


def load_quote_candidates(
    input_path: Path = DEFAULT_QUOTE_OUTPUT,
) -> List[QuoteCandidate]:
    if not input_path.exists():
        summary = verify_quotes_fixture_only(input_path)
        return list(summary["candidates"])

    data = json.loads(input_path.read_text(encoding="utf-8"))
    candidates: List[QuoteCandidate] = []
    for item in data.get("candidates", []):
        candidate = QuoteCandidate(
            evidence_id=str(item.get("evidence_id", "")),
            case_id=str(item.get("case_id", "")),
            phrase=str(item.get("phrase", "")),
            timestamp_start=str(item.get("timestamp_start", "")),
            timestamp_end=str(item.get("timestamp_end", "")),
            matched_text=str(item.get("matched_text", "")),
            raw_quote=str(item.get("raw_quote", "")),
            quote_confidence=float(item.get("quote_confidence", 0.0)),
            verification_status=str(item.get("verification_status", "")),
            verification_notes=str(item.get("verification_notes", "")),
        )
        validate_quote_candidate(candidate)
        candidates.append(candidate)
    return candidates


def link_from_quote_candidate(candidate: QuoteCandidate) -> CaseEvidenceLink:
    validate_quote_candidate(candidate)
    key = (candidate.evidence_id, candidate.raw_quote)
    target = FIXTURE_LINK_TARGETS.get(key)
    if candidate.verification_status == "quote_verified" and target:
        link = CaseEvidenceLink(
            case_id=target["case_id"],
            claim_id=target["claim_id"],
            evidence_id=candidate.evidence_id,
            quote_id=quote_id_for(candidate.evidence_id, candidate.raw_quote),
            phrase=candidate.phrase,
            timestamp_start=candidate.timestamp_start,
            timestamp_end=candidate.timestamp_end,
            raw_quote=candidate.raw_quote,
            link_status="link_verified",
            link_notes=(
                "TEST FIXTURE ONLY. Not real public evidence. "
                "Report readiness pending."
            ),
        )
    else:
        link = CaseEvidenceLink(
            case_id=candidate.case_id,
            claim_id=f"UNMAPPED_{candidate.evidence_id}_{slugify(candidate.raw_quote)}",
            evidence_id=candidate.evidence_id,
            quote_id=quote_id_for(candidate.evidence_id, candidate.raw_quote),
            phrase=candidate.phrase,
            timestamp_start=candidate.timestamp_start,
            timestamp_end=candidate.timestamp_end,
            raw_quote=candidate.raw_quote,
            link_status="link_unavailable",
            link_notes=(
                "TEST FIXTURE ONLY. No deterministic Case Evidence Linking v1 "
                "mapping exists for this quote. Not real public evidence."
            ),
        )
    validate_case_evidence_link(link)
    return link


def _evidence_by_id() -> Dict[str, EvidenceObject]:
    evidence_by_id: Dict[str, EvidenceObject] = {}
    for evidence in load_seed_evidence():
        validate_evidence_object(evidence)
        evidence_by_id[evidence.evidence_id] = evidence
    return evidence_by_id


def validate_report_sections_resolve(
    case: CaseObject,
    sections: List[ReportSection],
) -> None:
    case_data = case.to_dict()
    evidence_ids = {evidence["evidence_id"] for evidence in case_data["evidence"]}
    for section in sections:
        validate_report_section(section)
        if section.case_id != case.case_id:
            raise ValueError(
                f"ReportSection {section.section_id} case_id does not match {case.case_id}"
            )
        for evidence_id in section.evidence_ids:
            if evidence_id not in evidence_ids:
                raise ValueError(
                    f"ReportSection {section.section_id} references unknown "
                    f"evidence_id: {evidence_id}"
                )


def build_case_objects_from_links(
    links: List[CaseEvidenceLink],
) -> Tuple[List[CaseObject], List[ReportSection]]:
    evidence_by_id = _evidence_by_id()
    verified_links = [link for link in links if link.link_status == "link_verified"]
    cases: List[CaseObject] = []
    sections: List[ReportSection] = []

    for link in verified_links:
        target = FIXTURE_LINK_TARGETS[(link.evidence_id, link.raw_quote)]
        evidence = evidence_by_id[link.evidence_id]
        claim = ClaimObject(
            claim_id=link.claim_id,
            case_id=link.case_id,
            claim_type=target["claim_type"],
            text=target["claim_text"],
            evidence_ids=[link.evidence_id],
            verification_status="quote_linked_fixture",
        )
        validate_claim_object(claim)

        case = CaseObject(
            case_id=link.case_id,
            title=target["title"],
            domain=target["domain"],
            divergence_type=target["divergence_type"],
            claims=[claim],
            evidence=[evidence],
            evidence_strength=evidence.evidence_strength,
            verification_status="quote_linked_fixture",
        )
        validate_case_object(case)

        section = ReportSection(
            section_id=f"SECTION_{link.case_id}_QUOTE_LINK_FIXTURE",
            case_id=link.case_id,
            heading=target["title"],
            body=(
                "TEST FIXTURE ONLY. Draft report section link validation. "
                "Not real public evidence and not report-ready."
            ),
            evidence_ids=[link.evidence_id],
        )
        validate_report_sections_resolve(case, [section])

        cases.append(case)
        sections.append(section)

    return cases, sections


def write_case_evidence_links(
    links: List[CaseEvidenceLink],
    cases: List[CaseObject],
    sections: List[ReportSection],
    output_path: Path = DEFAULT_CASE_LINK_OUTPUT,
) -> Dict[str, Any]:
    for link in links:
        validate_case_evidence_link(link)
    for case in cases:
        validate_case_object(case)
        matching_sections = [section for section in sections if section.case_id == case.case_id]
        validate_report_sections_resolve(case, matching_sections)

    output = {
        "metadata": {
            "generated_at_utc": utc_now_iso(),
            "mode": "fixtures-only",
            "fixture_notice": "TEST FIXTURES ONLY. Not real public evidence.",
            "report_ready": False,
            "total_links": len(links),
        },
        "links": [link.to_dict() for link in links],
        "cases": [case.to_dict() for case in cases],
        "report_sections": [section.to_dict() for section in sections],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(output, str(output_path))
    return output


def link_case_evidence_fixture_only(
    output_path: Path = DEFAULT_CASE_LINK_OUTPUT,
) -> Dict[str, Any]:
    quote_candidates = load_quote_candidates()
    links = [link_from_quote_candidate(candidate) for candidate in quote_candidates]
    cases, sections = build_case_objects_from_links(links)
    write_case_evidence_links(links, cases, sections, output_path)

    return {
        "processed": len(quote_candidates),
        "link_candidate": sum(1 for link in links if link.link_status == "link_candidate"),
        "link_verified": sum(1 for link in links if link.link_status == "link_verified"),
        "link_rejected": sum(1 for link in links if link.link_status == "link_rejected"),
        "link_unavailable": sum(
            1 for link in links if link.link_status == "link_unavailable"
        ),
        "cases_built": len(cases),
        "claims_built": sum(len(case.claims) for case in cases),
        "report_sections_built": len(sections),
        "output_path": str(output_path),
        "links": links,
        "cases": cases,
        "report_sections": sections,
    }
