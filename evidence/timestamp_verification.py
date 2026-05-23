"""
timestamp_verification.py - Deterministic timestamp candidate validation.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import re

from evidence.evidence_loader import load_seed_evidence
from evidence.evidence_schema import save_json, validate_evidence_object
from evidence.transcript_acquisition import (
    TARGET_EVIDENCE_IDS,
    TranscriptAcquisitionArtifact,
    validate_transcript_artifact,
)


DEFAULT_TIMESTAMP_OUTPUT = Path("outputs/timestamps/timestamp_candidates.json")

TIMESTAMP_STATUSES = {
    "candidate_found",
    "timestamp_verified",
    "timestamp_rejected",
    "timestamp_unavailable",
}

TIMESTAMP_REQUIRED_STATUSES = {"candidate_found", "timestamp_verified"}
PROHIBITED_EVIDENCE_STATUSES = {"quote_verified", "report_ready"}


@dataclass
class TimestampCandidate:
    evidence_id: str
    case_id: str
    phrase: str
    timestamp_start: str
    timestamp_end: str
    matched_text: str
    match_confidence: float
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
    raise ValueError(f"Expected TimestampCandidate or dict, got {type(candidate).__name__}")


def normalize_text(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return " ".join(normalized.split())


def phrase_matches_text(phrase: str, matched_text: str) -> bool:
    if phrase.lower() in matched_text.lower():
        return True
    return normalize_text(phrase) in normalize_text(matched_text)


def timestamp_to_seconds(value: str, field_name: str) -> int:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"TimestampCandidate.{field_name} must be a non-empty string")

    parts = value.strip().split(":")
    if len(parts) == 2:
        hours = 0
        minutes, seconds = parts
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise ValueError(f"TimestampCandidate.{field_name} must be MM:SS or HH:MM:SS")

    try:
        h = int(hours)
        m = int(minutes)
        s = int(seconds)
    except ValueError as exc:
        raise ValueError(
            f"TimestampCandidate.{field_name} must contain numeric time parts"
        ) from exc

    if h < 0 or m < 0 or s < 0 or m >= 60 or s >= 60:
        raise ValueError(f"TimestampCandidate.{field_name} has invalid time parts")

    return h * 3600 + m * 60 + s


def validate_timestamp_candidate(candidate: Any) -> None:
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
            raise ValueError(f"TimestampCandidate.{field_name} must be a non-empty string")

    status = data["verification_status"]
    if status not in TIMESTAMP_STATUSES:
        raise ValueError(f"TimestampCandidate.verification_status is unsupported: {status}")

    confidence = data.get("match_confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError("TimestampCandidate.match_confidence must be between 0 and 1")

    evidence_status = data.get("evidence_verification_status")
    if evidence_status in PROHIBITED_EVIDENCE_STATUSES:
        raise ValueError(
            "Timestamp verification candidates cannot mark evidence as "
            f"{evidence_status}"
        )

    if status in TIMESTAMP_REQUIRED_STATUSES:
        for field_name in ("timestamp_start", "timestamp_end", "matched_text"):
            value = data.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"TimestampCandidate.{field_name} must be a non-empty string"
                )

        start = timestamp_to_seconds(data["timestamp_start"], "timestamp_start")
        end = timestamp_to_seconds(data["timestamp_end"], "timestamp_end")
        if end < start:
            raise ValueError("TimestampCandidate.timestamp_end must not be before start")

        if not phrase_matches_text(data["phrase"], data["matched_text"]):
            raise ValueError("TimestampCandidate.phrase must appear in matched_text")

    if status == "timestamp_unavailable":
        if not data["verification_notes"].strip():
            raise ValueError(
                "TimestampCandidate.timestamp_unavailable requires verification_notes"
            )


def candidate_from_segment(
    evidence_id: str,
    case_id: str,
    phrase: str,
    segment: Dict[str, Any],
) -> TimestampCandidate:
    candidate = TimestampCandidate(
        evidence_id=evidence_id,
        case_id=case_id,
        phrase=phrase,
        timestamp_start=str(segment.get("start", "")),
        timestamp_end=str(segment.get("end", "")),
        matched_text=str(segment.get("text", "")),
        match_confidence=1.0,
        verification_status="timestamp_verified",
        verification_notes=(
            "Deterministic fixture candidate only. Quote verification pending."
        ),
    )
    validate_timestamp_candidate(candidate)
    return candidate


def fixture_transcript_artifacts() -> List[TranscriptAcquisitionArtifact]:
    evidence_by_id = {
        evidence.evidence_id: evidence
        for evidence in load_seed_evidence()
        if evidence.evidence_id in TARGET_EVIDENCE_IDS
    }

    fixtures = {
        "VID_JOBS_001": {
            "language": "en",
            "segments": [
                {
                    "start": "00:00:10",
                    "end": "00:00:18",
                    "text": (
                        "We promised to create 500 000 new jobs in five years. "
                        "I dare not fail."
                    ),
                }
            ],
        },
        "VID_HEALTH_001": {
            "language": "en",
            "segments": [
                {
                    "start": "00:00:12",
                    "end": "00:00:20",
                    "text": (
                        "Botswana declared a public health emergency and secured "
                        "36 tonnes of medicines."
                    ),
                }
            ],
        },
    }

    artifacts: List[TranscriptAcquisitionArtifact] = []
    for evidence_id, fixture in fixtures.items():
        evidence = evidence_by_id[evidence_id]
        validate_evidence_object(evidence)
        transcript_text = " ".join(segment["text"] for segment in fixture["segments"])
        artifact = TranscriptAcquisitionArtifact(
            evidence_id=evidence.evidence_id,
            case_id=evidence.case_id,
            url=evidence.url,
            video_id=f"fixture-{evidence.evidence_id}",
            transcript_status="transcript_found",
            acquisition_method="timestamp-fixture-only",
            acquired_at_utc=utc_now_iso(),
            language=fixture["language"],
            transcript_text=transcript_text,
            segments=fixture["segments"],
            error="",
            verification_notes=(
                "TEST FIXTURE ONLY. Not real transcript evidence. "
                "Used only for deterministic timestamp validation."
            ),
        )
        validate_transcript_artifact(artifact)
        artifacts.append(artifact)

    return artifacts


def target_phrases_for_fixture(evidence_id: str) -> List[str]:
    phrases = {
        "VID_JOBS_001": ["500 000 new jobs", "I dare not fail"],
        "VID_HEALTH_001": ["public health emergency", "36 tonnes of medicines"],
    }
    return phrases.get(evidence_id, [])


def candidates_from_transcript_artifact(
    artifact: TranscriptAcquisitionArtifact,
) -> List[TimestampCandidate]:
    validate_transcript_artifact(artifact)
    candidates: List[TimestampCandidate] = []
    for phrase in target_phrases_for_fixture(artifact.evidence_id):
        matched_segment = None
        for segment in artifact.segments:
            if phrase_matches_text(phrase, str(segment.get("text", ""))):
                matched_segment = segment
                break

        if matched_segment is None:
            candidate = TimestampCandidate(
                evidence_id=artifact.evidence_id,
                case_id=artifact.case_id,
                phrase=phrase,
                timestamp_start="",
                timestamp_end="",
                matched_text="",
                match_confidence=0.0,
                verification_status="timestamp_unavailable",
                verification_notes=f"No fixture segment matched phrase: {phrase}",
            )
        else:
            candidate = candidate_from_segment(
                artifact.evidence_id,
                artifact.case_id,
                phrase,
                matched_segment,
            )

        validate_timestamp_candidate(candidate)
        candidates.append(candidate)

    return candidates


def write_timestamp_candidates(
    candidates: List[TimestampCandidate],
    output_path: Path = DEFAULT_TIMESTAMP_OUTPUT,
) -> Dict[str, Any]:
    for candidate in candidates:
        validate_timestamp_candidate(candidate)

    output = {
        "metadata": {
            "generated_at_utc": utc_now_iso(),
            "mode": "fixtures-only",
            "fixture_notice": "TEST FIXTURES ONLY. Not real transcript evidence.",
            "total_candidates": len(candidates),
        },
        "candidates": [candidate.to_dict() for candidate in candidates],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(output, str(output_path))
    return output


def verify_timestamps_fixture_only(
    output_path: Path = DEFAULT_TIMESTAMP_OUTPUT,
) -> Dict[str, Any]:
    artifacts = fixture_transcript_artifacts()
    candidates: List[TimestampCandidate] = []
    for artifact in artifacts:
        candidates.extend(candidates_from_transcript_artifact(artifact))

    write_timestamp_candidates(candidates, output_path)
    verified = sum(
        1 for candidate in candidates if candidate.verification_status == "timestamp_verified"
    )
    rejected = sum(
        1 for candidate in candidates if candidate.verification_status == "timestamp_rejected"
    )
    unavailable = sum(
        1 for candidate in candidates if candidate.verification_status == "timestamp_unavailable"
    )

    return {
        "processed": len(artifacts),
        "candidates_found": len(candidates),
        "timestamp_verified": verified,
        "timestamp_rejected": rejected,
        "timestamp_unavailable": unavailable,
        "output_path": str(output_path),
        "candidates": candidates,
    }
