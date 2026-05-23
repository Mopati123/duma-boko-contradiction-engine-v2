"""
transcript_acquisition.py - Safe transcript acquisition for EvidenceObjects.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse

from evidence.evidence_ingestion import (
    DEFAULT_TRANSCRIPT_DIR,
    load_evidence_objects,
    upgrade_evidence_status,
)
from evidence.evidence_schema import (
    EvidenceObject,
    TranscriptObject,
    save_json,
    validate_evidence_object,
)


TARGET_EVIDENCE_IDS = ("VID_JOBS_001", "VID_HEALTH_001")
TRANSCRIPT_STATUSES = {
    "pending",
    "transcript_found",
    "transcript_unavailable",
    "acquisition_failed",
}
FAILURE_STATUSES = {"transcript_unavailable", "acquisition_failed"}
PROHIBITED_EVIDENCE_STATUSES = {
    "timestamp_verified",
    "quote_verified",
    "report_ready",
}


@dataclass
class TranscriptAcquisitionArtifact:
    evidence_id: str
    case_id: str
    url: str
    video_id: str
    transcript_status: str
    acquisition_method: str
    acquired_at_utc: str
    language: str
    transcript_text: str
    segments: List[Dict[str, Any]]
    error: str
    verification_notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_artifact_dict(artifact: Any) -> Dict[str, Any]:
    if hasattr(artifact, "to_dict"):
        return artifact.to_dict()
    if isinstance(artifact, dict):
        return artifact
    raise ValueError(f"Expected transcript artifact, got {type(artifact).__name__}")


def extract_youtube_video_id(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    if host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        query_values = parse_qs(parsed.query).get("v", [])
        if query_values and query_values[0].strip():
            return query_values[0].strip()

        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts"}:
            return path_parts[1]

    if host == "youtu.be":
        path_parts = [part for part in parsed.path.split("/") if part]
        if path_parts:
            return path_parts[0]

    raise ValueError(f"Could not extract YouTube video ID from URL: {url}")


def normalize_segments(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    for entry in entries:
        text = str(entry.get("text", "")).strip()
        if not text:
            continue

        segment: Dict[str, Any] = {"text": text}
        if "start" in entry:
            segment["source_start"] = entry["start"]
        if "duration" in entry:
            segment["source_duration"] = entry["duration"]
        segments.append(segment)

    return segments


def transcript_text_from_segments(segments: List[Dict[str, Any]]) -> str:
    return " ".join(str(segment.get("text", "")).strip() for segment in segments).strip()


def validate_transcript_artifact(artifact: Any) -> None:
    data = _as_artifact_dict(artifact)
    required_keys = {
        "evidence_id",
        "case_id",
        "url",
        "video_id",
        "transcript_status",
        "acquisition_method",
        "acquired_at_utc",
        "language",
        "transcript_text",
        "segments",
        "error",
        "verification_notes",
    }

    missing = required_keys - set(data.keys())
    if missing:
        raise ValueError(f"Transcript artifact missing keys: {sorted(missing)}")

    for field_name in (
        "evidence_id",
        "case_id",
        "url",
        "video_id",
        "transcript_status",
        "acquisition_method",
        "acquired_at_utc",
        "language",
        "verification_notes",
    ):
        value = data[field_name]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"TranscriptArtifact.{field_name} must be a non-empty string")

    if data["transcript_status"] not in TRANSCRIPT_STATUSES:
        raise ValueError(
            f"TranscriptArtifact.transcript_status is unsupported: "
            f"{data['transcript_status']}"
        )

    if not isinstance(data["transcript_text"], str):
        raise ValueError("TranscriptArtifact.transcript_text must be a string")

    if not isinstance(data["error"], str):
        raise ValueError("TranscriptArtifact.error must be a string")

    if not isinstance(data["segments"], list):
        raise ValueError("TranscriptArtifact.segments must be a list")

    if data["transcript_status"] == "transcript_found":
        if not data["transcript_text"].strip():
            raise ValueError(
                "TranscriptArtifact.transcript_text must be non-empty when "
                "transcript_status=transcript_found"
            )

    if data["transcript_status"] in FAILURE_STATUSES:
        if data["transcript_text"].strip():
            raise ValueError(
                "TranscriptArtifact.transcript_text must be empty when transcript "
                "acquisition fails"
            )
        if not data["error"].strip():
            raise ValueError(
                "TranscriptArtifact.error must be non-empty when transcript "
                "acquisition fails"
            )

    evidence_status = data.get("verification_status")
    if evidence_status in PROHIBITED_EVIDENCE_STATUSES:
        raise ValueError(
            "Transcript acquisition artifacts cannot mark evidence as "
            f"{evidence_status}"
        )


def artifact_path_for(
    evidence_id: str,
    output_dir: Path = DEFAULT_TRANSCRIPT_DIR,
) -> Path:
    return output_dir / f"{evidence_id}.json"


def write_transcript_artifact(
    artifact: TranscriptAcquisitionArtifact,
    output_dir: Path = DEFAULT_TRANSCRIPT_DIR,
) -> Path:
    validate_transcript_artifact(artifact)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = artifact_path_for(artifact.evidence_id, output_dir)
    save_json(artifact.to_dict(), str(output_path))
    return output_path


def transcript_artifact_to_transcript_object(
    artifact: Any,
) -> TranscriptObject:
    validate_transcript_artifact(artifact)
    data = _as_artifact_dict(artifact)

    if data["transcript_status"] != "transcript_found":
        raise ValueError(
            f"{data['evidence_id']}: transcript_found is required before "
            "EvidenceObject upgrade"
        )

    return TranscriptObject(
        evidence_id=data["evidence_id"],
        transcript_status="transcribed",
        transcript_text=data["transcript_text"],
        source=artifact_path_for(data["evidence_id"]).as_posix(),
        generated_by=data["acquisition_method"],
        verification_notes=data["verification_notes"],
    )


def upgrade_evidence_from_transcript_artifact(
    evidence: EvidenceObject,
    artifact: Any,
) -> EvidenceObject:
    validate_evidence_object(evidence)
    data = _as_artifact_dict(artifact)
    transcript = transcript_artifact_to_transcript_object(data)
    upgraded = upgrade_evidence_status(evidence, "transcript_found", transcript)

    if upgraded.verification_status != "transcript_found":
        raise ValueError("Transcript acquisition can only upgrade to transcript_found")
    if upgraded.timestamp_start or upgraded.timestamp_end or upgraded.raw_quote:
        raise ValueError("Transcript acquisition cannot set timestamps or raw_quote")

    return upgraded


def transcript_found_artifact(
    evidence: EvidenceObject,
    entries: List[Dict[str, Any]],
    acquisition_method: str,
    language: str,
) -> TranscriptAcquisitionArtifact:
    validate_evidence_object(evidence)
    video_id = extract_youtube_video_id(evidence.url)
    segments = normalize_segments(entries)
    transcript_text = transcript_text_from_segments(segments)
    artifact = TranscriptAcquisitionArtifact(
        evidence_id=evidence.evidence_id,
        case_id=evidence.case_id,
        url=evidence.url,
        video_id=video_id,
        transcript_status="transcript_found",
        acquisition_method=acquisition_method,
        acquired_at_utc=utc_now_iso(),
        language=language,
        transcript_text=transcript_text,
        segments=segments,
        error="",
        verification_notes=(
            "Transcript text acquired. Timestamp and quote verification pending."
        ),
    )
    validate_transcript_artifact(artifact)
    return artifact


def failure_artifact(
    evidence: EvidenceObject,
    transcript_status: str,
    acquisition_method: str,
    error: str,
    language: str = "unknown",
) -> TranscriptAcquisitionArtifact:
    validate_evidence_object(evidence)
    if transcript_status not in FAILURE_STATUSES:
        raise ValueError(f"Unsupported transcript failure status: {transcript_status}")

    artifact = TranscriptAcquisitionArtifact(
        evidence_id=evidence.evidence_id,
        case_id=evidence.case_id,
        url=evidence.url,
        video_id=extract_youtube_video_id(evidence.url),
        transcript_status=transcript_status,
        acquisition_method=acquisition_method,
        acquired_at_utc=utc_now_iso(),
        language=language,
        transcript_text="",
        segments=[],
        error=error,
        verification_notes=(
            "No transcript text was acquired. Evidence remains source_found."
        ),
    )
    validate_transcript_artifact(artifact)
    return artifact


def fixture_artifact_for_evidence(evidence: EvidenceObject) -> TranscriptAcquisitionArtifact:
    if evidence.evidence_id == "VID_JOBS_001":
        return failure_artifact(
            evidence,
            "transcript_unavailable",
            "fixture",
            "Fixture mode does not fetch live transcript text.",
        )

    return failure_artifact(
        evidence,
        "acquisition_failed",
        "fixture",
        "Fixture mode simulates a safe acquisition failure.",
    )


def acquire_youtube_transcript(evidence: EvidenceObject) -> TranscriptAcquisitionArtifact:
    validate_evidence_object(evidence)

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except Exception as exc:
        return failure_artifact(
            evidence,
            "acquisition_failed",
            "youtube-transcript-api",
            f"youtube-transcript-api unavailable: {type(exc).__name__}: {exc}",
        )

    try:
        entries = YouTubeTranscriptApi.get_transcript(
            extract_youtube_video_id(evidence.url),
            languages=["en", "st", "tn"],
        )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        status = "transcript_unavailable"
        if type(exc).__name__ not in {"NoTranscriptFound", "TranscriptsDisabled"}:
            status = "acquisition_failed"
        return failure_artifact(
            evidence,
            status,
            "youtube-transcript-api",
            error,
        )

    return transcript_found_artifact(
        evidence,
        entries,
        "youtube-transcript-api",
        "unknown",
    )


def target_seed_evidence() -> List[EvidenceObject]:
    return [
        evidence
        for evidence in load_evidence_objects()
        if evidence.evidence_id in TARGET_EVIDENCE_IDS
    ]


def acquire_transcripts(
    fixtures_only: bool = False,
    output_dir: Path = DEFAULT_TRANSCRIPT_DIR,
) -> Dict[str, Any]:
    artifacts: List[TranscriptAcquisitionArtifact] = []
    for evidence in target_seed_evidence():
        if fixtures_only:
            artifact = fixture_artifact_for_evidence(evidence)
        else:
            artifact = acquire_youtube_transcript(evidence)

        write_transcript_artifact(artifact, output_dir)
        artifacts.append(artifact)

    counts = {status: 0 for status in TRANSCRIPT_STATUSES}
    for artifact in artifacts:
        counts[artifact.transcript_status] += 1

    return {
        "processed": len(artifacts),
        "transcript_found": counts["transcript_found"],
        "transcript_unavailable": counts["transcript_unavailable"],
        "acquisition_failed": counts["acquisition_failed"],
        "artifacts": artifacts,
    }
