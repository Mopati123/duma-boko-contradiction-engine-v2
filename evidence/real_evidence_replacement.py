"""
real_evidence_replacement.py - Conservative real evidence replacement lane.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json
import re

from evidence.evidence_loader import load_seed_evidence
from evidence.evidence_schema import EvidenceObject, save_json, validate_evidence_object
from evidence.quote_verification import quote_matches_text
from evidence.timestamp_verification import timestamp_to_seconds
from evidence.transcript_acquisition import (
    TARGET_EVIDENCE_IDS,
    acquire_youtube_transcript,
    extract_youtube_video_id,
)


REAL_TRANSCRIPT_DIR = Path("data/real_evidence_transcripts")
DEFAULT_REAL_EVIDENCE_OUTPUT_DIR = Path("outputs/real_evidence")
DEFAULT_REAL_STATUS_OUTPUT = (
    DEFAULT_REAL_EVIDENCE_OUTPUT_DIR / "real_evidence_status.json"
)
DEFAULT_REAL_TIMESTAMP_OUTPUT = (
    DEFAULT_REAL_EVIDENCE_OUTPUT_DIR / "real_timestamp_candidates.json"
)
DEFAULT_REAL_QUOTE_OUTPUT = (
    DEFAULT_REAL_EVIDENCE_OUTPUT_DIR / "real_quote_candidates.json"
)

REAL_EVIDENCE_STATUSES = {
    "transcript_found_real",
    "timestamp_candidate_real",
    "quote_candidate_real",
    "manual_review_required",
    "unavailable",
    "acquisition_failed",
}

TARGET_PHRASES = {
    "VID_JOBS_001": [
        "500 000 new jobs",
        "500,000 new jobs",
        "jobs in 5 years",
        "I dare not fail",
    ],
    "VID_HEALTH_001": [
        "public health emergency",
        "36 tonnes of medicines",
        "hospitals and clinics",
        "run out",
    ],
}

PROHIBITED_TEXT_CLAIMS = {
    "report_ready",
    "public_ready: true",
    "institution_ready",
    "institution-ready",
    "ready for public release",
    "ready for institutional release",
}


@dataclass
class RealEvidenceReplacementStatus:
    evidence_id: str
    case_id: str
    url: str
    acquisition_status: str
    transcript_status: str
    timestamp_status: str
    quote_status: str
    manual_review_required: bool
    public_ready: bool
    notes: str

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


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string")


def _string_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _string_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _string_values(item)


def _reject_overclaiming_text(data: Dict[str, Any], object_name: str) -> None:
    text = "\n".join(_string_values(data)).lower()
    for claim in PROHIBITED_TEXT_CLAIMS:
        if claim in text:
            raise ValueError(f"{object_name} contains prohibited readiness claim: {claim}")


def normalize_real_text(value: str) -> str:
    lower = value.lower().replace(",", "")
    lower = re.sub(r"(?<=\d)\s+(?=\d)", "", lower)
    normalized = re.sub(r"[^a-z0-9]+", " ", lower)
    return " ".join(normalized.split())


def phrase_matches_real_text(phrase: str, matched_text: str) -> bool:
    if phrase.lower() in matched_text.lower():
        return True
    return normalize_real_text(phrase) in normalize_real_text(matched_text)


def _items_for_evidence(items: Optional[Any], evidence_id: str) -> List[Dict[str, Any]]:
    if items is None:
        return []
    if isinstance(items, dict):
        if evidence_id in items:
            return [_as_dict(items[evidence_id])]
        for key in ("artifacts", "transcripts", "candidates", "statuses"):
            if key in items:
                return _items_for_evidence(items[key], evidence_id)
        return []
    return [
        _as_dict(item)
        for item in items
        if _as_dict(item).get("evidence_id") == evidence_id
    ]


def validate_real_evidence_replacement_status(
    status: Any,
    transcript_artifacts: Optional[Any] = None,
    timestamp_candidates: Optional[Any] = None,
    quote_candidates: Optional[Any] = None,
) -> None:
    data = _as_dict(status)
    object_name = "RealEvidenceReplacementStatus"

    for field_name in (
        "evidence_id",
        "case_id",
        "url",
        "acquisition_status",
        "transcript_status",
        "timestamp_status",
        "quote_status",
        "notes",
    ):
        _require_nonempty_string(data, field_name, object_name)

    for field_name in (
        "acquisition_status",
        "transcript_status",
        "timestamp_status",
        "quote_status",
    ):
        if data[field_name] not in REAL_EVIDENCE_STATUSES:
            raise ValueError(f"{object_name}.{field_name} is unsupported: {data[field_name]}")

    if data.get("manual_review_required") is not True:
        raise ValueError(
            "RealEvidenceReplacementStatus.manual_review_required must be true"
        )
    if data.get("public_ready") is not False:
        raise ValueError("RealEvidenceReplacementStatus.public_ready must be false")

    if data["transcript_status"] == "transcript_found_real":
        transcripts = _items_for_evidence(transcript_artifacts, data["evidence_id"])
        if not transcripts:
            raise ValueError(
                f"{data['evidence_id']}: transcript_found_real requires a real "
                "transcript artifact"
            )

    if data["timestamp_status"] == "timestamp_candidate_real":
        candidates = _items_for_evidence(timestamp_candidates, data["evidence_id"])
        if not candidates:
            raise ValueError(
                f"{data['evidence_id']}: timestamp_candidate_real requires a "
                "timestamp candidate"
            )
        for candidate in candidates:
            validate_real_timestamp_candidate(candidate)

    if data["quote_status"] == "quote_candidate_real":
        candidates = _items_for_evidence(quote_candidates, data["evidence_id"])
        if not candidates:
            raise ValueError(
                f"{data['evidence_id']}: quote_candidate_real requires a quote candidate"
            )
        for candidate in candidates:
            validate_real_quote_candidate(candidate)

    _reject_overclaiming_text(data, object_name)


def validate_real_transcript_artifact(artifact: Any) -> None:
    data = _as_dict(artifact)
    object_name = "RealTranscriptArtifact"

    for field_name in (
        "evidence_id",
        "case_id",
        "url",
        "video_id",
        "evidence_mode",
        "transcript_status",
        "acquisition_method",
        "acquired_at_utc",
        "language",
        "transcript_text",
        "notes",
    ):
        _require_nonempty_string(data, field_name, object_name)

    if data["evidence_mode"] != "real_source_transcript":
        raise ValueError("RealTranscriptArtifact.evidence_mode must be real_source_transcript")
    if data["transcript_status"] != "transcript_found_real":
        raise ValueError(
            "RealTranscriptArtifact.transcript_status must be transcript_found_real"
        )
    if data.get("manual_review_required") is not True:
        raise ValueError("RealTranscriptArtifact.manual_review_required must be true")
    if data.get("public_ready") is not False:
        raise ValueError("RealTranscriptArtifact.public_ready must be false")
    if not isinstance(data.get("segments"), list) or not data["segments"]:
        raise ValueError("RealTranscriptArtifact.segments must be a non-empty list")

    for segment in data["segments"]:
        if not isinstance(segment, dict):
            raise ValueError("RealTranscriptArtifact.segments must contain objects")
        _require_nonempty_string(segment, "text", "RealTranscriptArtifact.segment")

    _reject_overclaiming_text(data, object_name)


def validate_real_timestamp_candidate(candidate: Any) -> None:
    data = _as_dict(candidate)
    object_name = "RealTimestampCandidate"
    for field_name in (
        "evidence_id",
        "case_id",
        "phrase",
        "timestamp_start",
        "timestamp_end",
        "matched_text",
        "verification_status",
        "verification_notes",
    ):
        _require_nonempty_string(data, field_name, object_name)
    if data["verification_status"] != "timestamp_candidate_real":
        raise ValueError(
            "RealTimestampCandidate.verification_status must be timestamp_candidate_real"
        )
    if data.get("manual_review_required") is not True:
        raise ValueError("RealTimestampCandidate.manual_review_required must be true")
    if data.get("public_ready") is not False:
        raise ValueError("RealTimestampCandidate.public_ready must be false")
    confidence = data.get("match_confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError("RealTimestampCandidate.match_confidence must be between 0 and 1")

    start = timestamp_to_seconds(data["timestamp_start"], "timestamp_start")
    end = timestamp_to_seconds(data["timestamp_end"], "timestamp_end")
    if end < start:
        raise ValueError("RealTimestampCandidate.timestamp_end must not be before start")
    if not phrase_matches_real_text(data["phrase"], data["matched_text"]):
        raise ValueError("RealTimestampCandidate.phrase must appear in matched_text")

    _reject_overclaiming_text(data, object_name)


def validate_real_quote_candidate(candidate: Any) -> None:
    data = _as_dict(candidate)
    object_name = "RealQuoteCandidate"
    for field_name in (
        "evidence_id",
        "case_id",
        "phrase",
        "timestamp_start",
        "timestamp_end",
        "matched_text",
        "raw_quote",
        "verification_status",
        "verification_notes",
    ):
        _require_nonempty_string(data, field_name, object_name)
    if data["verification_status"] != "quote_candidate_real":
        raise ValueError(
            "RealQuoteCandidate.verification_status must be quote_candidate_real"
        )
    if data.get("manual_review_required") is not True:
        raise ValueError("RealQuoteCandidate.manual_review_required must be true")
    if data.get("public_ready") is not False:
        raise ValueError("RealQuoteCandidate.public_ready must be false")
    confidence = data.get("quote_confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError("RealQuoteCandidate.quote_confidence must be between 0 and 1")
    if not quote_matches_text(data["raw_quote"], data["matched_text"]):
        raise ValueError("RealQuoteCandidate.raw_quote must be contained in matched_text")

    _reject_overclaiming_text(data, object_name)


def target_seed_evidence(evidence_id: Optional[str] = None) -> List[EvidenceObject]:
    if evidence_id and evidence_id not in TARGET_EVIDENCE_IDS:
        raise ValueError(f"Unsupported evidence_id for real replacement: {evidence_id}")
    evidence = [
        item
        for item in load_seed_evidence()
        if item.evidence_id in TARGET_EVIDENCE_IDS
    ]
    if evidence_id:
        evidence = [item for item in evidence if item.evidence_id == evidence_id]
    for item in evidence:
        validate_evidence_object(item)
    return evidence


def real_transcript_path(
    evidence_id: str,
    transcript_dir: Path = REAL_TRANSCRIPT_DIR,
) -> Path:
    return transcript_dir / f"{evidence_id}.json"


def load_real_transcript_artifact(
    evidence: EvidenceObject,
    transcript_dir: Path = REAL_TRANSCRIPT_DIR,
) -> Optional[Dict[str, Any]]:
    path = real_transcript_path(evidence.evidence_id, transcript_dir)
    if not path.exists():
        return None
    artifact = json.loads(path.read_text(encoding="utf-8"))
    validate_real_transcript_artifact(artifact)
    if artifact["evidence_id"] != evidence.evidence_id:
        raise ValueError(f"{path}: evidence_id does not match {evidence.evidence_id}")
    if artifact["case_id"] != evidence.case_id:
        raise ValueError(f"{path}: case_id does not match {evidence.case_id}")
    if artifact["url"] != evidence.url:
        raise ValueError(f"{path}: url does not match seed EvidenceObject")
    return artifact


def real_transcript_artifact_from_acquisition(evidence: EvidenceObject, artifact: Any) -> Dict[str, Any]:
    acquisition = _as_dict(artifact)
    if acquisition.get("transcript_status") != "transcript_found":
        raise ValueError(f"{evidence.evidence_id}: live acquisition did not find transcript")
    real_artifact = {
        "evidence_id": evidence.evidence_id,
        "case_id": evidence.case_id,
        "url": evidence.url,
        "video_id": extract_youtube_video_id(evidence.url),
        "evidence_mode": "real_source_transcript",
        "transcript_status": "transcript_found_real",
        "acquisition_method": str(acquisition.get("acquisition_method", "")),
        "acquired_at_utc": str(acquisition.get("acquired_at_utc", utc_now_iso())),
        "language": str(acquisition.get("language", "unknown")),
        "transcript_text": str(acquisition.get("transcript_text", "")),
        "segments": list(acquisition.get("segments", [])),
        "manual_review_required": True,
        "public_ready": False,
        "notes": (
            "REAL SOURCE TRANSCRIPT. Auto-acquired transcript text requires manual "
            "review before any publication use."
        ),
    }
    validate_real_transcript_artifact(real_artifact)
    return real_artifact


def write_real_transcript_artifact(
    artifact: Dict[str, Any],
    transcript_dir: Path = REAL_TRANSCRIPT_DIR,
) -> Path:
    validate_real_transcript_artifact(artifact)
    transcript_dir.mkdir(parents=True, exist_ok=True)
    output_path = real_transcript_path(artifact["evidence_id"], transcript_dir)
    save_json(artifact, str(output_path))
    return output_path


def _format_seconds(total_seconds: float) -> str:
    seconds = int(round(total_seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining = seconds % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{remaining:02d}"
    return f"{minutes:02d}:{remaining:02d}"


def _segment_timestamps(segment: Dict[str, Any]) -> Optional[tuple[str, str]]:
    start = segment.get("start")
    end = segment.get("end")
    if isinstance(start, str) and start.strip() and isinstance(end, str) and end.strip():
        return start.strip(), end.strip()

    numeric_start = segment.get("source_start", segment.get("start"))
    numeric_duration = segment.get("source_duration", segment.get("duration"))
    if isinstance(numeric_start, (int, float)) and isinstance(numeric_duration, (int, float)):
        return (
            _format_seconds(float(numeric_start)),
            _format_seconds(float(numeric_start) + float(numeric_duration)),
        )
    return None


def real_timestamp_candidates_from_transcript(
    artifact: Dict[str, Any],
) -> List[Dict[str, Any]]:
    validate_real_transcript_artifact(artifact)
    candidates: List[Dict[str, Any]] = []
    for phrase in TARGET_PHRASES.get(artifact["evidence_id"], []):
        for segment in artifact["segments"]:
            matched_text = str(segment.get("text", ""))
            timestamps = _segment_timestamps(segment)
            if phrase_matches_real_text(phrase, matched_text) and timestamps:
                candidate = {
                    "evidence_id": artifact["evidence_id"],
                    "case_id": artifact["case_id"],
                    "phrase": phrase,
                    "timestamp_start": timestamps[0],
                    "timestamp_end": timestamps[1],
                    "matched_text": matched_text,
                    "match_confidence": 0.85,
                    "verification_status": "timestamp_candidate_real",
                    "verification_notes": (
                        "REAL SOURCE TRANSCRIPT. Timestamp candidate only; manual "
                        "review required before publication use."
                    ),
                    "manual_review_required": True,
                    "public_ready": False,
                }
                validate_real_timestamp_candidate(candidate)
                candidates.append(candidate)
                break
    return candidates


def real_quote_candidates_from_timestamps(
    timestamp_candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for timestamp_candidate in timestamp_candidates:
        validate_real_timestamp_candidate(timestamp_candidate)
        candidate = {
            "evidence_id": timestamp_candidate["evidence_id"],
            "case_id": timestamp_candidate["case_id"],
            "phrase": timestamp_candidate["phrase"],
            "timestamp_start": timestamp_candidate["timestamp_start"],
            "timestamp_end": timestamp_candidate["timestamp_end"],
            "matched_text": timestamp_candidate["matched_text"],
            "raw_quote": timestamp_candidate["phrase"],
            "quote_confidence": 0.85,
            "verification_status": "quote_candidate_real",
            "verification_notes": (
                "REAL SOURCE TRANSCRIPT. Quote candidate only; manual review "
                "required before publication use."
            ),
            "manual_review_required": True,
            "public_ready": False,
        }
        validate_real_quote_candidate(candidate)
        candidates.append(candidate)
    return candidates


def write_real_evidence_outputs(
    statuses: List[RealEvidenceReplacementStatus],
    transcript_artifacts: List[Dict[str, Any]],
    timestamp_candidates: List[Dict[str, Any]],
    quote_candidates: List[Dict[str, Any]],
    output_dir: Path = DEFAULT_REAL_EVIDENCE_OUTPUT_DIR,
    mode: str = "dry-run",
) -> Dict[str, str]:
    for status in statuses:
        validate_real_evidence_replacement_status(
            status,
            transcript_artifacts=transcript_artifacts,
            timestamp_candidates=timestamp_candidates,
            quote_candidates=quote_candidates,
        )
    for candidate in timestamp_candidates:
        validate_real_timestamp_candidate(candidate)
    for candidate in quote_candidates:
        validate_real_quote_candidate(candidate)

    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / "real_evidence_status.json"
    timestamp_path = output_dir / "real_timestamp_candidates.json"
    quote_path = output_dir / "real_quote_candidates.json"

    metadata = {
        "generated_at_utc": utc_now_iso(),
        "mode": mode,
        "manual_review_required": True,
        "public_ready": False,
    }
    save_json(
        {
            "metadata": metadata,
            "statuses": [status.to_dict() for status in statuses],
        },
        str(status_path),
    )
    save_json(
        {
            "metadata": {**metadata, "total_candidates": len(timestamp_candidates)},
            "candidates": timestamp_candidates,
        },
        str(timestamp_path),
    )
    save_json(
        {
            "metadata": {**metadata, "total_candidates": len(quote_candidates)},
            "candidates": quote_candidates,
        },
        str(quote_path),
    )
    return {
        "status_output": str(status_path),
        "timestamp_output": str(timestamp_path),
        "quote_output": str(quote_path),
    }


def replace_real_evidence(
    *,
    dry_run: bool,
    live: bool = False,
    evidence_id: Optional[str] = None,
    transcript_dir: Path = REAL_TRANSCRIPT_DIR,
    output_dir: Path = DEFAULT_REAL_EVIDENCE_OUTPUT_DIR,
) -> Dict[str, Any]:
    if dry_run == live:
        raise ValueError("Choose exactly one mode: dry_run or live")

    statuses: List[RealEvidenceReplacementStatus] = []
    transcript_artifacts: List[Dict[str, Any]] = []
    timestamp_candidates: List[Dict[str, Any]] = []
    quote_candidates: List[Dict[str, Any]] = []

    for evidence in target_seed_evidence(evidence_id):
        transcript_artifact = None
        acquisition_status = "manual_review_required"
        transcript_status = "unavailable"
        notes = (
            "No real transcript artifact found. Manual review required before "
            "real evidence replacement."
        )

        if live:
            acquired = acquire_youtube_transcript(evidence)
            if acquired.transcript_status == "transcript_found":
                transcript_artifact = real_transcript_artifact_from_acquisition(
                    evidence,
                    acquired,
                )
                write_real_transcript_artifact(transcript_artifact, transcript_dir)
                acquisition_status = "transcript_found_real"
                transcript_status = "transcript_found_real"
                notes = (
                    "Real transcript artifact acquired. Manual review required before "
                    "publication use."
                )
            else:
                acquisition_status = (
                    "acquisition_failed"
                    if acquired.transcript_status == "acquisition_failed"
                    else "unavailable"
                )
                transcript_status = acquisition_status
                notes = acquired.error or "Live transcript acquisition did not return text."
        else:
            transcript_artifact = load_real_transcript_artifact(evidence, transcript_dir)
            if transcript_artifact:
                transcript_artifacts.append(transcript_artifact)
                acquisition_status = "transcript_found_real"
                transcript_status = "transcript_found_real"
                notes = (
                    "Existing real transcript artifact loaded. Manual review required "
                    "before publication use."
                )

        evidence_timestamps: List[Dict[str, Any]] = []
        evidence_quotes: List[Dict[str, Any]] = []
        if transcript_artifact:
            if transcript_artifact not in transcript_artifacts:
                transcript_artifacts.append(transcript_artifact)
            evidence_timestamps = real_timestamp_candidates_from_transcript(
                transcript_artifact
            )
            evidence_quotes = real_quote_candidates_from_timestamps(evidence_timestamps)
            timestamp_candidates.extend(evidence_timestamps)
            quote_candidates.extend(evidence_quotes)

        status = RealEvidenceReplacementStatus(
            evidence_id=evidence.evidence_id,
            case_id=evidence.case_id,
            url=evidence.url,
            acquisition_status=acquisition_status,
            transcript_status=transcript_status,
            timestamp_status=(
                "timestamp_candidate_real" if evidence_timestamps else "unavailable"
            ),
            quote_status="quote_candidate_real" if evidence_quotes else "unavailable",
            manual_review_required=True,
            public_ready=False,
            notes=notes,
        )
        validate_real_evidence_replacement_status(
            status,
            transcript_artifacts=transcript_artifacts,
            timestamp_candidates=timestamp_candidates,
            quote_candidates=quote_candidates,
        )
        statuses.append(status)

    outputs = write_real_evidence_outputs(
        statuses,
        transcript_artifacts,
        timestamp_candidates,
        quote_candidates,
        output_dir,
        "live" if live else "dry-run",
    )
    return {
        "processed": len(statuses),
        "transcript_found_real": sum(
            1 for status in statuses if status.transcript_status == "transcript_found_real"
        ),
        "timestamp_candidate_real": len(timestamp_candidates),
        "quote_candidate_real": len(quote_candidates),
        "manual_review_required": sum(
            1 for status in statuses if status.manual_review_required
        ),
        "unavailable": sum(
            1
            for status in statuses
            if "unavailable"
            in {
                status.acquisition_status,
                status.transcript_status,
                status.timestamp_status,
                status.quote_status,
            }
        ),
        "acquisition_failed": sum(
            1 for status in statuses if status.acquisition_status == "acquisition_failed"
        ),
        "statuses": statuses,
        "timestamp_candidates": timestamp_candidates,
        "quote_candidates": quote_candidates,
        **outputs,
    }
