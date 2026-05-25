"""
canonical_case_model.py - Candidate-only canonical six-block case models.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json

import yaml

from evidence.evidence_loader import load_seed_evidence
from evidence.health_fallback_source import (
    DEFAULT_HEALTH_FALLBACK_SOURCE_STATUS_OUTPUT,
    PRIMARY_HEALTH_FALLBACK_CANDIDATE_ID,
)
from evidence.selected_recovery_source import load_selected_recovery_sources
from evidence.source_content_verification import (
    DEFAULT_SOURCE_CONTENT_VERIFICATION_STATUS_OUTPUT,
)


DEFAULT_CANONICAL_CASE_MODEL_OUTPUT_DIR = Path("outputs/canonical_case_models")
DEFAULT_CANONICAL_CASE_MODELS_OUTPUT = (
    DEFAULT_CANONICAL_CASE_MODEL_OUTPUT_DIR / "canonical_case_models.json"
)
DEFAULT_CANONICAL_CASE_MODEL_SUMMARY_OUTPUT = (
    DEFAULT_CANONICAL_CASE_MODEL_OUTPUT_DIR / "canonical_case_model_summary.json"
)
DEFAULT_TARGETS_PATH = Path("config/contradiction_targets.yaml")
DEFAULT_CASES_OUTPUT_PATH = Path("outputs/cases/divergence_cases.json")

SOURCE_TYPES = {
    "radio_interview",
    "tv_interview",
    "campaign_rally",
    "social_media_post",
    "budget_speech",
    "parliament_speech",
    "manifesto",
    "official_statement",
    "news_article",
    "other",
}

SOURCE_STATUSES = {
    "candidate_unverified",
    "source_reachable",
    "source_blocked",
    "source_unavailable",
    "pending_manual_review",
}

OWNERSHIP_TYPES = {
    "official_government_source",
    "official_party_source",
    "independent_media",
    "social_media",
    "third_party",
    "unknown",
}

CORRELATION_LEVELS = {"high", "medium", "low", "unknown"}

CONTENT_VERIFICATION_STATUSES = {
    "candidate_unverified",
    "verified_for_content_review",
    "pending_manual_review",
    "rejected",
}

AUTHORITY_CONTEXTS = {
    "candidate",
    "party_leader",
    "president",
    "minister",
    "member_of_parliament",
    "government_official",
    "unknown",
}

PROMISE_CATEGORIES = {
    "health",
    "economy",
    "employment",
    "education",
    "energy",
    "water",
    "transport",
    "social_welfare",
    "governance",
    "other",
}

MEASURABILITY_STATUSES = {
    "measurable",
    "partially_measurable",
    "directional",
    "aspirational",
    "unknown",
}

POSITION_TYPES = {
    "current_public_statement",
    "denial",
    "delay",
    "justification",
    "backtracking",
    "outcome_failure",
    "policy_shift",
    "distancing",
    "not_yet_assessed",
}

POSITION_STATUSES = {
    "candidate_unverified",
    "verified_for_content_review",
    "pending_manual_review",
    "unavailable",
}

EVIDENCE_TYPES = {
    "video",
    "audio",
    "transcript",
    "screenshot",
    "official_statement",
    "media_article",
    "diagnostic_artifact",
}

EVIDENCE_REFERENCE_STATUSES = {
    "candidate_unverified",
    "verified_for_content_review",
    "pending_manual_review",
    "blocked",
    "unavailable",
    "approved",
}

CONTRADICTION_TYPES = {
    "statement_vs_statement",
    "promise_vs_outcome",
    "promise_vs_delay",
    "promise_vs_justification",
    "party_identity_vs_government_position",
    "official_commitment_vs_nonbinding_claim",
    "not_yet_assessed",
}

SEVERITIES = {"low", "medium", "high", "critical", "not_assessed"}

DIVERGENCE_STATUSES = {
    "candidate_unverified",
    "partial_verification",
    "pending_manual_review",
    "insufficient_evidence",
    "verified_for_content_review",
}

MODEL_VERIFICATION_STATUSES = {
    "candidate_unverified",
    "verified_for_content_review",
    "pending_manual_review",
    "insufficient_evidence",
}

CASE_STATUSES = {
    "candidate_model",
    "pending_manual_review",
    "content_review_candidate",
    "insufficient_evidence",
}

FORBIDDEN_MODEL_CLAIMS = (
    "verified_for_approval_review",
    "approved_evidence: true",
    "public_ready: true",
    "institutional_ready: true",
    "report_ready: true",
    "ready for public release",
    "ready for institutional release",
    "public-ready",
    "institution-ready",
    "final forensic report",
)


@dataclass
class SourceDetails:
    source_type: str
    source_title: str
    source_date: str
    source_platform: str
    source_url: str
    source_reference_id: str
    source_status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SourceOwnership:
    ownership_type: str
    correlation_level: str
    verification_status: str
    ownership_notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SpeakerPoliticalLeader:
    speaker_name: str
    speaker_role: str
    political_party: str
    authority_context: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OriginalPromise:
    promise_category: str
    exact_promise_quote: str
    word_for_word_transcript: str
    promise_timeframe: str
    promise_summary: str
    measurability_status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CurrentGovernmentPosition:
    position_type: str
    current_statement_quote: str
    current_outcome_summary: str
    current_date: str
    current_source_url: str
    position_status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceReference:
    evidence_id: str
    evidence_type: str
    source_url: str
    status: str
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceCollection:
    video: List[EvidenceReference]
    audio: List[EvidenceReference]
    transcript: List[EvidenceReference]
    screenshots: List[EvidenceReference]
    official_statements: List[EvidenceReference]
    media_articles: List[EvidenceReference]
    source_diagnostics: List[EvidenceReference]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video": [item.to_dict() for item in self.video],
            "audio": [item.to_dict() for item in self.audio],
            "transcript": [item.to_dict() for item in self.transcript],
            "screenshots": [item.to_dict() for item in self.screenshots],
            "official_statements": [
                item.to_dict() for item in self.official_statements
            ],
            "media_articles": [item.to_dict() for item in self.media_articles],
            "source_diagnostics": [
                item.to_dict() for item in self.source_diagnostics
            ],
        }


@dataclass
class ContradictionAnalysis:
    contradiction_type: str
    analysis_summary: str
    severity: str
    divergence_status: str
    evidence_gap_notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CanonicalCaseModel:
    case_id: str
    topic: str
    source_details: SourceDetails
    source_ownership: SourceOwnership
    speaker: SpeakerPoliticalLeader
    original_promise: OriginalPromise
    current_government_position: CurrentGovernmentPosition
    evidence_collection: EvidenceCollection
    contradiction_analysis: ContradictionAnalysis
    verification_status: str
    case_status: str
    approved_evidence: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    requires_manual_review: bool
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "topic": self.topic,
            "source_details": self.source_details.to_dict(),
            "source_ownership": self.source_ownership.to_dict(),
            "speaker": self.speaker.to_dict(),
            "original_promise": self.original_promise.to_dict(),
            "current_government_position": self.current_government_position.to_dict(),
            "evidence_collection": self.evidence_collection.to_dict(),
            "contradiction_analysis": self.contradiction_analysis.to_dict(),
            "verification_status": self.verification_status,
            "case_status": self.case_status,
            "approved_evidence": self.approved_evidence,
            "public_ready": self.public_ready,
            "institutional_ready": self.institutional_ready,
            "report_ready": self.report_ready,
            "requires_manual_review": self.requires_manual_review,
            "notes": self.notes,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_dict(value: Any) -> Dict[str, Any]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    raise ValueError(f"Expected object or dict, got {type(value).__name__}")


def _string_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _string_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _string_values(item)


def _contains_key(value: Any, target_key: str) -> bool:
    if isinstance(value, dict):
        return target_key in value or any(
            _contains_key(item, target_key) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_key(item, target_key) for item in value)
    return False


def _require_key(data: Dict[str, Any], field_name: str) -> None:
    if field_name not in data:
        raise ValueError(f"CanonicalCaseModel.{field_name} is required")


def _require_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    if field_name not in data or not isinstance(data[field_name], str):
        raise ValueError(f"{object_name}.{field_name} must be a string")


def _require_nonempty_string(
    data: Dict[str, Any],
    field_name: str,
    object_name: str,
) -> None:
    _require_string(data, field_name, object_name)
    if not data[field_name].strip():
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string")


def _reject_forbidden_claims(data: Dict[str, Any]) -> None:
    if _contains_key(data, "verified_for_approval_review"):
        raise ValueError("CanonicalCaseModel must not contain verified_for_approval_review")
    text = "\n".join(_string_values(data)).lower()
    for claim in FORBIDDEN_MODEL_CLAIMS:
        if claim in text:
            raise ValueError(
                "CanonicalCaseModel contains prohibited approval/readiness claim: "
                f"{claim}"
            )


def validate_source_details(value: Any) -> None:
    data = _as_dict(value)
    for field_name in (
        "source_type",
        "source_title",
        "source_date",
        "source_platform",
        "source_url",
        "source_reference_id",
        "source_status",
    ):
        _require_string(data, field_name, "SourceDetails")
    if data["source_type"] not in SOURCE_TYPES:
        raise ValueError(f"SourceDetails.source_type is unsupported: {data['source_type']}")
    if data["source_status"] not in SOURCE_STATUSES:
        raise ValueError(
            f"SourceDetails.source_status is unsupported: {data['source_status']}"
        )


def validate_source_ownership(value: Any) -> None:
    data = _as_dict(value)
    for field_name in (
        "ownership_type",
        "correlation_level",
        "verification_status",
        "ownership_notes",
    ):
        _require_string(data, field_name, "SourceOwnership")
    if data["ownership_type"] not in OWNERSHIP_TYPES:
        raise ValueError(
            f"SourceOwnership.ownership_type is unsupported: {data['ownership_type']}"
        )
    if data["correlation_level"] not in CORRELATION_LEVELS:
        raise ValueError(
            "SourceOwnership.correlation_level is unsupported: "
            f"{data['correlation_level']}"
        )
    if data["verification_status"] not in CONTENT_VERIFICATION_STATUSES:
        raise ValueError(
            "SourceOwnership.verification_status is unsupported: "
            f"{data['verification_status']}"
        )


def validate_speaker(value: Any) -> None:
    data = _as_dict(value)
    for field_name in (
        "speaker_name",
        "speaker_role",
        "political_party",
        "authority_context",
    ):
        _require_string(data, field_name, "SpeakerPoliticalLeader")
    if data["authority_context"] not in AUTHORITY_CONTEXTS:
        raise ValueError(
            "SpeakerPoliticalLeader.authority_context is unsupported: "
            f"{data['authority_context']}"
        )


def validate_original_promise(value: Any) -> None:
    data = _as_dict(value)
    for field_name in (
        "promise_category",
        "exact_promise_quote",
        "word_for_word_transcript",
        "promise_timeframe",
        "promise_summary",
        "measurability_status",
    ):
        _require_string(data, field_name, "OriginalPromise")
    if data["promise_category"] not in PROMISE_CATEGORIES:
        raise ValueError(
            f"OriginalPromise.promise_category is unsupported: {data['promise_category']}"
        )
    if data["measurability_status"] not in MEASURABILITY_STATUSES:
        raise ValueError(
            "OriginalPromise.measurability_status is unsupported: "
            f"{data['measurability_status']}"
        )


def validate_current_position(value: Any) -> None:
    data = _as_dict(value)
    for field_name in (
        "position_type",
        "current_statement_quote",
        "current_outcome_summary",
        "current_date",
        "current_source_url",
        "position_status",
    ):
        _require_string(data, field_name, "CurrentGovernmentPosition")
    if data["position_type"] not in POSITION_TYPES:
        raise ValueError(
            "CurrentGovernmentPosition.position_type is unsupported: "
            f"{data['position_type']}"
        )
    if data["position_status"] not in POSITION_STATUSES:
        raise ValueError(
            "CurrentGovernmentPosition.position_status is unsupported: "
            f"{data['position_status']}"
        )


def validate_evidence_reference(value: Any) -> None:
    data = _as_dict(value)
    for field_name in ("evidence_id", "evidence_type", "source_url", "status", "notes"):
        _require_string(data, field_name, "EvidenceReference")
    if data["evidence_type"] not in EVIDENCE_TYPES:
        raise ValueError(
            f"EvidenceReference.evidence_type is unsupported: {data['evidence_type']}"
        )
    if data["status"] not in EVIDENCE_REFERENCE_STATUSES:
        raise ValueError(f"EvidenceReference.status is unsupported: {data['status']}")


def validate_evidence_collection(value: Any) -> None:
    data = _as_dict(value)
    for field_name in (
        "video",
        "audio",
        "transcript",
        "screenshots",
        "official_statements",
        "media_articles",
        "source_diagnostics",
    ):
        if field_name not in data or not isinstance(data[field_name], list):
            raise ValueError(f"EvidenceCollection.{field_name} must be a list")
        for item in data[field_name]:
            validate_evidence_reference(item)


def validate_contradiction_analysis(value: Any) -> None:
    data = _as_dict(value)
    for field_name in (
        "contradiction_type",
        "analysis_summary",
        "severity",
        "divergence_status",
        "evidence_gap_notes",
    ):
        _require_string(data, field_name, "ContradictionAnalysis")
    if data["contradiction_type"] not in CONTRADICTION_TYPES:
        raise ValueError(
            "ContradictionAnalysis.contradiction_type is unsupported: "
            f"{data['contradiction_type']}"
        )
    if data["severity"] not in SEVERITIES:
        raise ValueError(
            f"ContradictionAnalysis.severity is unsupported: {data['severity']}"
        )
    if data["divergence_status"] not in DIVERGENCE_STATUSES:
        raise ValueError(
            "ContradictionAnalysis.divergence_status is unsupported: "
            f"{data['divergence_status']}"
        )


def validate_canonical_case_model(model: Any) -> None:
    data = _as_dict(model)

    for field_name in (
        "case_id",
        "topic",
        "source_details",
        "source_ownership",
        "speaker",
        "original_promise",
        "current_government_position",
        "evidence_collection",
        "contradiction_analysis",
        "verification_status",
        "case_status",
        "notes",
    ):
        _require_key(data, field_name)

    _require_nonempty_string(data, "case_id", "CanonicalCaseModel")
    _require_nonempty_string(data, "topic", "CanonicalCaseModel")
    _require_nonempty_string(data, "verification_status", "CanonicalCaseModel")
    _require_nonempty_string(data, "case_status", "CanonicalCaseModel")
    _require_nonempty_string(data, "notes", "CanonicalCaseModel")

    validate_source_details(data["source_details"])
    validate_source_ownership(data["source_ownership"])
    validate_speaker(data["speaker"])
    validate_original_promise(data["original_promise"])
    validate_current_position(data["current_government_position"])
    validate_evidence_collection(data["evidence_collection"])
    validate_contradiction_analysis(data["contradiction_analysis"])

    if data["verification_status"] not in MODEL_VERIFICATION_STATUSES:
        raise ValueError(
            "CanonicalCaseModel.verification_status is unsupported: "
            f"{data['verification_status']}"
        )
    if data["case_status"] not in CASE_STATUSES:
        raise ValueError(
            f"CanonicalCaseModel.case_status is unsupported: {data['case_status']}"
        )

    if data.get("requires_manual_review") is not True:
        raise ValueError("CanonicalCaseModel.requires_manual_review must be true")
    if data.get("approved_evidence") is not False:
        raise ValueError("CanonicalCaseModel.approved_evidence must be false")
    if data.get("public_ready") is not False:
        raise ValueError("CanonicalCaseModel.public_ready must be false")
    if data.get("institutional_ready") is not False:
        raise ValueError("CanonicalCaseModel.institutional_ready must be false")
    if data.get("report_ready") is not False:
        raise ValueError("CanonicalCaseModel.report_ready must be false")

    _reject_forbidden_claims(data)


def _safe_records_from_json(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        records = payload.get("records", [])
    elif isinstance(payload, list):
        records = payload
    else:
        return []
    return [record for record in records if isinstance(record, dict)]


def _load_targets(path: Path = DEFAULT_TARGETS_PATH) -> List[Dict[str, str]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    targets = data.get("targets", [])
    if not isinstance(targets, list):
        raise ValueError("contradiction_targets.yaml must contain targets")
    normalized: List[Dict[str, str]] = []
    for target in targets:
        if not isinstance(target, dict):
            raise ValueError("Each contradiction target must be an object")
        normalized.append(
            {
                "case_id": str(target.get("case_id", "")),
                "topic": str(target.get("topic", "")),
                "divergence_type": str(target.get("divergence_type", "")),
                "description": " ".join(str(target.get("description", "")).split()),
            }
        )
    return normalized


def _load_case_output(path: Path = DEFAULT_CASES_OUTPUT_PATH) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases", []) if isinstance(payload, dict) else payload
    if not isinstance(cases, list):
        return {}
    return {
        str(case.get("case_id")): case
        for case in cases
        if isinstance(case, dict) and case.get("case_id")
    }


def _category_for_topic(topic: str) -> str:
    if topic == "jobs_creation":
        return "employment"
    if topic == "healthcare_reform":
        return "health"
    if topic in {"manifesto_contract", "anti_corruption"}:
        return "governance"
    if topic == "economic_diversification":
        return "economy"
    return "other"


def _measurability_for_topic(topic: str) -> str:
    if topic == "jobs_creation":
        return "measurable"
    if topic in {"healthcare_reform", "economic_diversification"}:
        return "partially_measurable"
    if topic in {"manifesto_contract", "anti_corruption"}:
        return "directional"
    return "unknown"


def _position_type_for_topic(topic: str, has_health_candidate: bool) -> str:
    if topic == "healthcare_reform" and has_health_candidate:
        return "outcome_failure"
    if topic == "manifesto_contract":
        return "denial"
    return "not_yet_assessed"


def _contradiction_type(raw_type: str, topic: str) -> str:
    if raw_type == "promise_vs_outcome":
        return "promise_vs_outcome"
    if raw_type == "obligation_denial" or topic == "manifesto_contract":
        return "official_commitment_vs_nonbinding_claim"
    if raw_type == "economic_constraint_justification":
        return "promise_vs_justification"
    if raw_type == "governance_distancing":
        return "statement_vs_statement"
    return "not_yet_assessed"


def _evidence_status_from_verification(status: str) -> str:
    if status == "verified_candidate_for_content_review":
        return "verified_for_content_review"
    if status == "blocked_pending_fallback":
        return "blocked"
    if status == "extraction_unavailable":
        return "unavailable"
    return "pending_manual_review"


def _source_status_from_verification(status: str) -> str:
    if status == "verified_candidate_for_content_review":
        return "source_reachable"
    if status == "blocked_pending_fallback":
        return "source_blocked"
    if status == "extraction_unavailable":
        return "source_unavailable"
    return "pending_manual_review"


def _content_verification_status(status: str) -> str:
    if status == "verified_candidate_for_content_review":
        return "verified_for_content_review"
    if status == "rejected":
        return "rejected"
    if status in {"not_checked", "blocked_pending_fallback", "extraction_unavailable"}:
        return "pending_manual_review"
    return "candidate_unverified"


def _reference(
    evidence_id: str,
    evidence_type: str,
    source_url: str,
    status: str,
    notes: str,
) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        source_url=source_url,
        status=status,
        notes=notes,
    )


def _blank_collection() -> EvidenceCollection:
    return EvidenceCollection(
        video=[],
        audio=[],
        transcript=[],
        screenshots=[],
        official_statements=[],
        media_articles=[],
        source_diagnostics=[],
    )


def _records_by_evidence_id(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {
        str(record.get("original_evidence_id")): record
        for record in records
        if record.get("original_evidence_id")
    }


def _selected_by_evidence_id() -> Dict[str, Any]:
    try:
        selected = load_selected_recovery_sources()
    except Exception:
        return {}
    return {
        "VID_JOBS_001": next(
            (
                record
                for record in selected
                if record.original_evidence_id == "VID_JOBS_001"
            ),
            None,
        ),
        "VID_HEALTH_001": next(
            (
                record
                for record in selected
                if record.original_evidence_id == "VID_HEALTH_001"
            ),
            None,
        ),
    }


def _seed_by_case_id() -> Dict[str, Any]:
    return {item.case_id: item for item in load_seed_evidence()}


def _build_case_model(
    target: Dict[str, str],
    seed_by_case: Dict[str, Any],
    selected_by_evidence: Dict[str, Any],
    source_verification_by_evidence: Dict[str, Dict[str, Any]],
    health_fallback_by_evidence: Dict[str, Dict[str, Any]],
    case_outputs: Dict[str, Dict[str, Any]],
) -> CanonicalCaseModel:
    case_id = target["case_id"]
    topic = target["topic"]
    seed = seed_by_case.get(case_id)
    evidence_id = seed.evidence_id if seed else ""
    seed_url = seed.url if seed else ""
    seed_title = seed.title if seed else ""
    seed_platform = seed.platform if seed else ""
    seed_speaker = seed.speaker or "" if seed else ""

    source_url = seed_url
    source_title = seed_title
    source_type = "other"
    source_platform = seed_platform
    source_reference_id = evidence_id
    ownership_type = "unknown"
    correlation_level = "unknown"
    ownership_verification = "pending_manual_review"
    source_status = "pending_manual_review"
    verification_status = "pending_manual_review"
    case_status = "pending_manual_review"
    divergence_status = "pending_manual_review"
    evidence_status = "pending_manual_review"
    extracted_text = ""
    extracted_quote = ""

    selected = selected_by_evidence.get(evidence_id)
    source_record = source_verification_by_evidence.get(evidence_id, {})
    health_record = health_fallback_by_evidence.get("VID_HEALTH_001", {})
    health_verified = (
        case_id == "CASE_006"
        and health_record.get("fallback_candidate_id")
        == PRIMARY_HEALTH_FALLBACK_CANDIDATE_ID
        and health_record.get("verification_status")
        == "verified_candidate_for_content_review"
    )

    if case_id == "CASE_002" and selected is not None:
        source_url = selected.selected_source_url
        source_title = "UDC selected recovery source"
        source_type = "manifesto"
        source_platform = "web"
        source_reference_id = selected.selected_recovery_candidate_id
        ownership_type = "official_party_source"
        correlation_level = "high"
        selected_status = str(source_record.get("verification_status", ""))
        source_status = _source_status_from_verification(selected_status)
        ownership_verification = _content_verification_status(selected_status)
        evidence_status = _evidence_status_from_verification(selected_status)
        if selected_status == "verified_candidate_for_content_review":
            verification_status = "verified_for_content_review"
            case_status = "content_review_candidate"
            divergence_status = "verified_for_content_review"
            extracted_text = str(source_record.get("extracted_text_candidate", ""))
            extracted_quote = str(source_record.get("extracted_quote_candidate", ""))
        else:
            verification_status = "pending_manual_review"
            divergence_status = "pending_manual_review"

    elif case_id == "CASE_006":
        if health_verified:
            source_url = str(health_record.get("fallback_source_url", ""))
            source_title = "Al Jazeera health fallback source"
            source_type = "news_article"
            source_platform = "web"
            source_reference_id = str(health_record.get("fallback_candidate_id", ""))
            ownership_type = "independent_media"
            correlation_level = "medium"
            source_status = "source_reachable"
            ownership_verification = "verified_for_content_review"
            verification_status = "verified_for_content_review"
            case_status = "content_review_candidate"
            divergence_status = "partial_verification"
            evidence_status = "verified_for_content_review"
            extracted_text = str(health_record.get("extracted_text_candidate", ""))
            extracted_quote = str(health_record.get("extracted_quote_candidate", ""))
        elif selected is not None:
            source_url = selected.selected_source_url
            source_title = "Reuters selected recovery source"
            source_type = "news_article"
            source_platform = "web"
            source_reference_id = selected.selected_recovery_candidate_id
            ownership_type = "independent_media"
            correlation_level = "high"
            ownership_verification = "pending_manual_review"
            source_status = "source_blocked"
            evidence_status = "blocked"
            divergence_status = "pending_manual_review"

    elif case_id == "CASE_001":
        source_type = "manifesto"
        source_platform = "local_config"
        source_title = "Manifesto-contract investigation theme"
        source_status = "pending_manual_review"
        ownership_type = "official_party_source"
        correlation_level = "unknown"

    category = _category_for_topic(topic)
    measurability = _measurability_for_topic(topic)
    case_output = case_outputs.get(case_id, {})
    analysis_summary = str(case_output.get("analysis", "")).strip()
    if not analysis_summary:
        analysis_summary = (
            "Canonical six-block model candidate generated from local case "
            "configuration. Manual evidence review is required."
        )

    collection = _blank_collection()
    if seed:
        collection.video.append(
            _reference(
                evidence_id=seed.evidence_id,
                evidence_type="video",
                source_url=seed.url,
                status="candidate_unverified",
                notes="Seed video reference retained for manual evidence review.",
            )
        )
    if selected is not None and case_id in {"CASE_002", "CASE_006"}:
        ref_type = "official_statement" if case_id == "CASE_002" else "media_article"
        target_list = (
            collection.official_statements
            if ref_type == "official_statement"
            else collection.media_articles
        )
        target_list.append(
            _reference(
                evidence_id=selected.selected_recovery_candidate_id,
                evidence_type=ref_type,
                source_url=selected.selected_source_url,
                status=evidence_status,
                notes="Selected recovery source retained as candidate-only reference.",
            )
        )
    if health_record and case_id == "CASE_006":
        collection.media_articles.append(
            _reference(
                evidence_id=str(health_record.get("fallback_candidate_id", "")),
                evidence_type="media_article",
                source_url=str(health_record.get("fallback_source_url", "")),
                status=_evidence_status_from_verification(
                    str(health_record.get("verification_status", ""))
                ),
                notes="Health fallback source diagnostic reference; human review required.",
            )
        )
    if source_record:
        collection.source_diagnostics.append(
            _reference(
                evidence_id=f"{evidence_id}_SOURCE_CONTENT_VERIFICATION",
                evidence_type="diagnostic_artifact",
                source_url=str(DEFAULT_SOURCE_CONTENT_VERIFICATION_STATUS_OUTPUT),
                status=_evidence_status_from_verification(
                    str(source_record.get("verification_status", ""))
                ),
                notes="Local source-content verification diagnostic artifact.",
            )
        )
    if health_record and case_id == "CASE_006":
        collection.source_diagnostics.append(
            _reference(
                evidence_id="VID_HEALTH_001_HEALTH_FALLBACK_SOURCE",
                evidence_type="diagnostic_artifact",
                source_url=str(DEFAULT_HEALTH_FALLBACK_SOURCE_STATUS_OUTPUT),
                status=_evidence_status_from_verification(
                    str(health_record.get("verification_status", ""))
                ),
                notes="Local health fallback source diagnostic artifact.",
            )
        )

    model = CanonicalCaseModel(
        case_id=case_id,
        topic=topic,
        source_details=SourceDetails(
            source_type=source_type,
            source_title=source_title,
            source_date="",
            source_platform=source_platform,
            source_url=source_url,
            source_reference_id=source_reference_id,
            source_status=source_status,
        ),
        source_ownership=SourceOwnership(
            ownership_type=ownership_type,
            correlation_level=correlation_level,
            verification_status=ownership_verification,
            ownership_notes=(
                "Ownership classification is candidate-only and requires manual review."
            ),
        ),
        speaker=SpeakerPoliticalLeader(
            speaker_name=seed_speaker or "unknown",
            speaker_role="political leader" if seed_speaker else "unknown",
            political_party="UDC" if case_id in {"CASE_001", "CASE_002"} else "unknown",
            authority_context="candidate" if seed_speaker else "unknown",
        ),
        original_promise=OriginalPromise(
            promise_category=category,
            exact_promise_quote=extracted_quote if case_id == "CASE_002" else "",
            word_for_word_transcript="",
            promise_timeframe="five years" if case_id == "CASE_002" else "",
            promise_summary=target["description"],
            measurability_status=measurability,
        ),
        current_government_position=CurrentGovernmentPosition(
            position_type=_position_type_for_topic(topic, health_verified),
            current_statement_quote="" if not health_verified else extracted_quote,
            current_outcome_summary=extracted_text if health_verified else target["description"],
            current_date="",
            current_source_url=source_url if health_verified else "",
            position_status=(
                "verified_for_content_review" if health_verified else "pending_manual_review"
            ),
        ),
        evidence_collection=collection,
        contradiction_analysis=ContradictionAnalysis(
            contradiction_type=_contradiction_type(target["divergence_type"], topic),
            analysis_summary=analysis_summary,
            severity="not_assessed",
            divergence_status=divergence_status,
            evidence_gap_notes=(
                "No approved evidence has been attached. Manual transcript, quote, "
                "timestamp, and context review remain required."
            ),
        ),
        verification_status=verification_status,
        case_status=case_status,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Candidate-only canonical six-block model. This is not an approval "
            "or readiness decision."
        ),
    )
    validate_canonical_case_model(model)
    return model


def summarize_canonical_case_models(
    models: List[CanonicalCaseModel],
) -> Dict[str, Any]:
    for model in models:
        validate_canonical_case_model(model)

    return {
        "generated_at_utc": utc_now_iso(),
        "case_model_count": len(models),
        "six_block_complete_count": sum(1 for model in models if has_six_blocks(model)),
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
        "requires_manual_review_count": sum(
            1 for model in models if model.requires_manual_review
        ),
        "content_review_candidate_count": sum(
            1
            for model in models
            if model.verification_status == "verified_for_content_review"
        ),
    }


def has_six_blocks(model: Any) -> bool:
    data = _as_dict(model)
    return all(
        key in data
        for key in (
            "source_details",
            "source_ownership",
            "speaker",
            "original_promise",
            "current_government_position",
            "evidence_collection",
        )
    )


def write_canonical_case_model_outputs(
    models: List[CanonicalCaseModel],
    output_dir: Path = DEFAULT_CANONICAL_CASE_MODEL_OUTPUT_DIR,
) -> Dict[str, str]:
    for model in models:
        validate_canonical_case_model(model)

    output_dir.mkdir(parents=True, exist_ok=True)
    models_path = output_dir / "canonical_case_models.json"
    summary_path = output_dir / "canonical_case_model_summary.json"
    summary = summarize_canonical_case_models(models)
    summary["models_output"] = str(models_path)
    summary["summary_output"] = str(summary_path)

    payload = {
        "metadata": {
            "generated_at_utc": summary["generated_at_utc"],
            "schema_version": "CanonicalCaseModel.v1",
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
            "report_ready": False,
        },
        "case_models": [model.to_dict() for model in models],
    }
    models_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return {"models_output": str(models_path), "summary_output": str(summary_path)}


def build_canonical_case_models(
    case_id: Optional[str] = None,
    no_network: bool = False,
    targets_path: Path = DEFAULT_TARGETS_PATH,
    source_verification_path: Path = DEFAULT_SOURCE_CONTENT_VERIFICATION_STATUS_OUTPUT,
    health_fallback_path: Path = DEFAULT_HEALTH_FALLBACK_SOURCE_STATUS_OUTPUT,
    output_dir: Path = DEFAULT_CANONICAL_CASE_MODEL_OUTPUT_DIR,
) -> Dict[str, Any]:
    del no_network  # This lane never performs network access.
    targets = _load_targets(targets_path)
    if case_id:
        targets = [target for target in targets if target["case_id"] == case_id]
        if not targets:
            raise ValueError(f"Unknown case_id for canonical case model: {case_id}")

    seed_by_case = _seed_by_case_id()
    selected_by_evidence = _selected_by_evidence_id()
    source_verification_by_evidence = _records_by_evidence_id(
        _safe_records_from_json(source_verification_path)
    )
    health_fallback_by_evidence = _records_by_evidence_id(
        _safe_records_from_json(health_fallback_path)
    )
    case_outputs = _load_case_output()

    models = [
        _build_case_model(
            target,
            seed_by_case=seed_by_case,
            selected_by_evidence=selected_by_evidence,
            source_verification_by_evidence=source_verification_by_evidence,
            health_fallback_by_evidence=health_fallback_by_evidence,
            case_outputs=case_outputs,
        )
        for target in targets
    ]
    outputs = write_canonical_case_model_outputs(models, output_dir=output_dir)
    summary = summarize_canonical_case_models(models)
    summary["case_ids"] = [model.case_id for model in models]
    summary["case_categories"] = {
        model.case_id: model.original_promise.promise_category for model in models
    }
    summary["case_statuses"] = {model.case_id: model.case_status for model in models}
    summary.update(outputs)
    return summary
