"""
quote_verification.py - Deterministic quote candidate validation.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from evidence.evidence_schema import save_json
from evidence.timestamp_verification import (
    DEFAULT_TIMESTAMP_OUTPUT,
    TimestampCandidate,
    normalize_text,
    timestamp_to_seconds,
    validate_timestamp_candidate,
    verify_timestamps_fixture_only,
)


DEFAULT_QUOTE_OUTPUT = Path("outputs/quotes/quote_candidates.json")

QUOTE_STATUSES = {
    "quote_candidate_found",
    "quote_verified",
    "quote_rejected",
    "quote_unavailable",
}

QUOTE_REQUIRED_STATUSES = {"quote_candidate_found", "quote_verified"}
REASON_REQUIRED_STATUSES = {"quote_rejected", "quote_unavailable"}
PROHIBITED_EVIDENCE_STATUSES = {"report_ready"}


@dataclass
class QuoteCandidate:
    evidence_id: str
    case_id: str
    phrase: str
    timestamp_start: str
    timestamp_end: str
    matched_text: str
    raw_quote: str
    quote_confidence: float
    verification_status: str
    verification_notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_dict(candidate: Any) -> Dict[str, Any]:
    if hasattr(candidate, "to_dict"):
        return candidate.to_dict()
    if isinstance(candidate, dict):
        return candidate
    raise ValueError(f"Expected QuoteCandidate or dict, got {type(candidate).__name__}")


def quote_matches_text(raw_quote: str, matched_text: str) -> bool:
    quote = normalize_text(raw_quote)
    text = normalize_text(matched_text)
    return quote in text or text in quote


def validate_quote_candidate(candidate: Any) -> None:
    data = _as_dict(candidate)

    for field_name in (
        "evidence_id",
        "case_id",
        "phrase",
        "verification_status",
        "verification_notes",
    ):
        value = data.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"QuoteCandidate.{field_name} must be a non-empty string")

    status = data["verification_status"]
    if status not in QUOTE_STATUSES:
        raise ValueError(f"QuoteCandidate.verification_status is unsupported: {status}")

    confidence = data.get("quote_confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError("QuoteCandidate.quote_confidence must be between 0 and 1")

    evidence_status = data.get("evidence_verification_status")
    if evidence_status in PROHIBITED_EVIDENCE_STATUSES or data.get("report_ready"):
        raise ValueError("Quote verification candidates cannot mark evidence as report_ready")

    matched_text = data.get("matched_text")
    if not isinstance(matched_text, str) or not matched_text.strip():
        raise ValueError("QuoteCandidate.matched_text must be a non-empty string")

    if status in QUOTE_REQUIRED_STATUSES:
        for field_name in ("raw_quote", "timestamp_start", "timestamp_end"):
            value = data.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"QuoteCandidate.{field_name} must be a non-empty string")

        start = timestamp_to_seconds(data["timestamp_start"], "timestamp_start")
        end = timestamp_to_seconds(data["timestamp_end"], "timestamp_end")
        if end < start:
            raise ValueError("QuoteCandidate.timestamp_end must not be before start")

        if not quote_matches_text(data["raw_quote"], matched_text):
            raise ValueError("QuoteCandidate.raw_quote must be contained in matched_text")

    if status in REASON_REQUIRED_STATUSES:
        if not data["verification_notes"].strip():
            raise ValueError(
                f"QuoteCandidate.{status} requires verification_notes"
            )


def quote_candidate_from_timestamp(
    timestamp_candidate: TimestampCandidate,
) -> QuoteCandidate:
    validate_timestamp_candidate(timestamp_candidate)
    if timestamp_candidate.verification_status != "timestamp_verified":
        candidate = QuoteCandidate(
            evidence_id=timestamp_candidate.evidence_id,
            case_id=timestamp_candidate.case_id,
            phrase=timestamp_candidate.phrase,
            timestamp_start=timestamp_candidate.timestamp_start,
            timestamp_end=timestamp_candidate.timestamp_end,
            matched_text=timestamp_candidate.matched_text,
            raw_quote="",
            quote_confidence=0.0,
            verification_status="quote_unavailable",
            verification_notes=(
                "Timestamp candidate is not timestamp_verified; quote unavailable."
            ),
        )
        validate_quote_candidate(candidate)
        return candidate

    candidate = QuoteCandidate(
        evidence_id=timestamp_candidate.evidence_id,
        case_id=timestamp_candidate.case_id,
        phrase=timestamp_candidate.phrase,
        timestamp_start=timestamp_candidate.timestamp_start,
        timestamp_end=timestamp_candidate.timestamp_end,
        matched_text=timestamp_candidate.matched_text,
        raw_quote=timestamp_candidate.phrase,
        quote_confidence=1.0,
        verification_status="quote_verified",
        verification_notes=(
            "TEST FIXTURE ONLY. Not real quote evidence. "
            "Used only for deterministic Quote Verification v1 validation. "
            "Report readiness pending."
        ),
    )
    validate_quote_candidate(candidate)
    return candidate


def load_timestamp_candidates_from_output(
    input_path: Path = DEFAULT_TIMESTAMP_OUTPUT,
) -> List[TimestampCandidate]:
    if not input_path.exists():
        summary = verify_timestamps_fixture_only(input_path)
        return list(summary["candidates"])

    import json

    data = json.loads(input_path.read_text(encoding="utf-8"))
    candidates: List[TimestampCandidate] = []
    for item in data.get("candidates", []):
        candidate = TimestampCandidate(
            evidence_id=str(item.get("evidence_id", "")),
            case_id=str(item.get("case_id", "")),
            phrase=str(item.get("phrase", "")),
            timestamp_start=str(item.get("timestamp_start", "")),
            timestamp_end=str(item.get("timestamp_end", "")),
            matched_text=str(item.get("matched_text", "")),
            match_confidence=float(item.get("match_confidence", 0.0)),
            verification_status=str(item.get("verification_status", "")),
            verification_notes=str(item.get("verification_notes", "")),
        )
        validate_timestamp_candidate(candidate)
        candidates.append(candidate)
    return candidates


def write_quote_candidates(
    candidates: List[QuoteCandidate],
    output_path: Path = DEFAULT_QUOTE_OUTPUT,
) -> Dict[str, Any]:
    for candidate in candidates:
        validate_quote_candidate(candidate)

    output = {
        "metadata": {
            "generated_at_utc": utc_now_iso(),
            "mode": "fixtures-only",
            "fixture_notice": "TEST FIXTURES ONLY. Not real quote evidence.",
            "report_ready": False,
            "total_candidates": len(candidates),
        },
        "candidates": [candidate.to_dict() for candidate in candidates],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(output, str(output_path))
    return output


def verify_quotes_fixture_only(
    output_path: Path = DEFAULT_QUOTE_OUTPUT,
) -> Dict[str, Any]:
    timestamp_candidates = load_timestamp_candidates_from_output()
    quote_candidates = [
        quote_candidate_from_timestamp(candidate) for candidate in timestamp_candidates
    ]

    write_quote_candidates(quote_candidates, output_path)
    candidate_found = sum(
        1
        for candidate in quote_candidates
        if candidate.verification_status == "quote_candidate_found"
    )
    verified = sum(
        1 for candidate in quote_candidates if candidate.verification_status == "quote_verified"
    )
    rejected = sum(
        1 for candidate in quote_candidates if candidate.verification_status == "quote_rejected"
    )
    unavailable = sum(
        1
        for candidate in quote_candidates
        if candidate.verification_status == "quote_unavailable"
    )

    return {
        "processed": len(timestamp_candidates),
        "quote_candidate_found": candidate_found,
        "quote_verified": verified,
        "quote_rejected": rejected,
        "quote_unavailable": unavailable,
        "output_path": str(output_path),
        "candidates": quote_candidates,
    }
