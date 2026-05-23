"""
evidence_schema.py - Stable JSON schema definitions for evidence cases.

v3.0: Reframed to "Governance Divergence" engine. 
Added GovernanceDivergenceCase and refined EvidencePosition.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
import json


PLACEHOLDER_URL_MARKERS = (
    "example.com",
    "example1",
    "example2",
    "youtube.com/watch?v=example",
    "todo",
    "placeholder",
)

TIMESTAMP_VERIFIED_STATUSES = {
    "timestamp_verified",
    "quote_verified",
    "report_ready",
}

QUOTE_VERIFIED_STATUSES = {
    "quote_verified",
    "report_ready",
}


def _as_dict(value: Any) -> Dict[str, Any]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    raise ValueError(f"Expected object or dict, got {type(value).__name__}")


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string")


def _require_nonempty_list(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{object_name}.{field_name} must be a non-empty list")


def _url_has_placeholder(url: str) -> bool:
    lower_url = url.lower()
    return any(marker in lower_url for marker in PLACEHOLDER_URL_MARKERS)


@dataclass
class EvidencePosition:
    """A single evidence position (promise or outcome)."""
    quote: str
    source: str
    url: str
    date: str
    evidence_type: str                 # "manifesto", "article", "video", "speech"
    platform: str                      # "youtube", "facebook", "news", "transcript"
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None
    screenshot_path: Optional[str] = None
    confidence: float = 0.0
    speaker: str = "Duma Boko"
    matched_terms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceObject:
    """Canonical v1 evidence record used by reportable claims."""
    evidence_id: str
    case_id: str
    source_type: str
    platform: str
    title: str
    url: str
    evidence_role: str
    verification_status: str
    evidence_strength: str
    speaker: Optional[str] = None
    speaker_confidence: Optional[str] = None
    target_phrases: List[str] = field(default_factory=list)
    transcript_status: Optional[str] = None
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None
    raw_quote: Optional[str] = None
    context_before: Optional[str] = None
    context_after: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ClaimObject:
    """A reportable claim linked to one or more evidence records."""
    claim_id: str
    case_id: str
    claim_type: str
    text: str
    evidence_ids: List[str]
    verification_status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CaseObject:
    """A complete v1 evidence-backed divergence case."""
    case_id: str
    title: str
    domain: str
    divergence_type: str
    claims: List[ClaimObject]
    evidence: List[EvidenceObject]
    evidence_strength: str
    verification_status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReportSection:
    """A report section that must cite supporting evidence."""
    section_id: str
    case_id: str
    heading: str
    body: str
    evidence_ids: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GovernanceDivergenceCase:
    """
    A complete divergence case from the reconstruction engine.
    """
    case_id: str
    topic: str

    # Evidence positions (Reframed)
    promise: Dict[str, Any]             # EvidencePosition.to_dict()
    outcome_or_position: Dict[str, Any] # EvidencePosition.to_dict()

    # Divergence details
    divergence_type: str                # from new taxonomy
    analysis: str                       # detailed reconstruction
    evidence_strength: str              # "low", "medium", "high"
    verification_status: str            # "verified", "partial", "pending"

    # Supporting data
    description: str = ""
    all_promise_sources: List[Dict[str, Any]] = field(default_factory=list)
    all_outcome_sources: List[Dict[str, Any]] = field(default_factory=list)
    raw_urls: List[str] = field(default_factory=list)
    evidence_objects: List[Dict[str, Any]] = field(default_factory=list)
    claim_evidence_links: Dict[str, List[str]] = field(default_factory=dict)

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    pipeline_version: str = "divergence_engine_v3.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def validate_evidence_object(evidence: Any) -> None:
    data = _as_dict(evidence)
    object_name = "EvidenceObject"

    for field_name in (
        "evidence_id",
        "case_id",
        "source_type",
        "platform",
        "title",
        "url",
        "evidence_role",
        "verification_status",
        "evidence_strength",
    ):
        _require_nonempty_string(data, field_name, object_name)

    url = data["url"]
    if _url_has_placeholder(url):
        raise ValueError(f"EvidenceObject.url appears to be a placeholder: {url}")

    status = data["verification_status"].strip()
    if status in TIMESTAMP_VERIFIED_STATUSES:
        if not data.get("timestamp_start") or not data.get("timestamp_end"):
            raise ValueError(
                f"EvidenceObject with verification_status={status} requires "
                "timestamp_start and timestamp_end"
            )

    if status in QUOTE_VERIFIED_STATUSES and not data.get("raw_quote"):
        raise ValueError(
            f"EvidenceObject with verification_status={status} requires raw_quote"
        )


def validate_claim_object(claim: Any) -> None:
    data = _as_dict(claim)
    object_name = "ClaimObject"

    for field_name in (
        "claim_id",
        "case_id",
        "claim_type",
        "text",
        "verification_status",
    ):
        _require_nonempty_string(data, field_name, object_name)

    _require_nonempty_list(data, "evidence_ids", object_name)


def validate_case_object(case: Any) -> None:
    data = _as_dict(case)
    object_name = "CaseObject"

    for field_name in (
        "case_id",
        "title",
        "domain",
        "divergence_type",
        "evidence_strength",
        "verification_status",
    ):
        _require_nonempty_string(data, field_name, object_name)

    _require_nonempty_list(data, "claims", object_name)
    _require_nonempty_list(data, "evidence", object_name)

    evidence_ids = set()
    for evidence in data["evidence"]:
        validate_evidence_object(evidence)
        evidence_data = _as_dict(evidence)
        evidence_ids.add(evidence_data["evidence_id"])

    for claim in data["claims"]:
        validate_claim_object(claim)
        claim_data = _as_dict(claim)
        for evidence_id in claim_data["evidence_ids"]:
            if evidence_id not in evidence_ids:
                raise ValueError(
                    f"CaseObject claim {claim_data['claim_id']} references "
                    f"unknown evidence_id: {evidence_id}"
                )


def validate_report_section(section: Any) -> None:
    data = _as_dict(section)
    object_name = "ReportSection"

    for field_name in (
        "section_id",
        "case_id",
        "heading",
        "body",
    ):
        _require_nonempty_string(data, field_name, object_name)

    _require_nonempty_list(data, "evidence_ids", object_name)


# JSON Utilities
class EvidenceEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        return super().default(obj)

def save_json(data: Any, filepath: str) -> None:
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, cls=EvidenceEncoder, indent=2, ensure_ascii=False)

def load_json(filepath: str) -> Any:
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)
