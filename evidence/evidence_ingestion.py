"""
evidence_ingestion.py - Non-downloading EvidenceObject ingestion helpers.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from evidence.evidence_loader import DEFAULT_INDEX_PATH, build_evidence_index
from evidence.evidence_schema import (
    EvidenceObject,
    TranscriptObject,
    load_json,
    validate_evidence_object,
    validate_transcript_object,
)


DEFAULT_TRANSCRIPT_DIR = Path("data/evidence_transcripts")

STATUS_TRANSITIONS = {
    "source_found": "transcript_found",
    "transcript_found": "timestamp_verified",
    "timestamp_verified": "quote_verified",
    "quote_verified": "report_ready",
}

IMMUTABLE_EVIDENCE_FIELDS = ("evidence_id", "case_id", "url", "title")


def evidence_object_from_dict(data: Dict[str, Any]) -> EvidenceObject:
    return EvidenceObject(
        evidence_id=str(data.get("evidence_id", "")),
        case_id=str(data.get("case_id", "")),
        source_type=str(data.get("source_type", "")),
        platform=str(data.get("platform", "")),
        title=str(data.get("title", "")),
        url=str(data.get("url", "")),
        evidence_role=str(data.get("evidence_role", "")),
        verification_status=str(data.get("verification_status", "")),
        evidence_strength=str(data.get("evidence_strength", "")),
        speaker=data.get("speaker"),
        speaker_confidence=data.get("speaker_confidence"),
        target_phrases=list(data.get("target_phrases") or []),
        transcript_status=data.get("transcript_status"),
        timestamp_start=data.get("timestamp_start"),
        timestamp_end=data.get("timestamp_end"),
        raw_quote=data.get("raw_quote"),
        context_before=data.get("context_before"),
        context_after=data.get("context_after"),
        notes=data.get("notes"),
    )


def coerce_evidence_object(evidence: Any) -> EvidenceObject:
    if isinstance(evidence, EvidenceObject):
        validate_evidence_object(evidence)
        return evidence
    if isinstance(evidence, dict):
        coerced = evidence_object_from_dict(evidence)
        validate_evidence_object(coerced)
        return coerced
    raise ValueError(f"Expected EvidenceObject or dict, got {type(evidence).__name__}")


def load_or_build_evidence_index(
    index_path: Path = DEFAULT_INDEX_PATH,
) -> Dict[str, Any]:
    if index_path.exists():
        index = load_json(str(index_path))
    else:
        index = build_evidence_index(output_path=index_path)

    evidence_items = index.get("evidence")
    if not isinstance(evidence_items, list) or not evidence_items:
        raise ValueError("evidence_index.json must contain a non-empty evidence list")

    for item in evidence_items:
        validate_evidence_object(coerce_evidence_object(item))

    return index


def load_evidence_objects(index_path: Path = DEFAULT_INDEX_PATH) -> List[EvidenceObject]:
    index = load_or_build_evidence_index(index_path)
    return [coerce_evidence_object(item) for item in index["evidence"]]


def load_transcript_artifact(
    evidence_id: str,
    transcript_dir: Path = DEFAULT_TRANSCRIPT_DIR,
) -> Optional[TranscriptObject]:
    path = transcript_dir / f"{evidence_id}.txt"
    if not path.exists():
        return None

    metadata: Dict[str, str] = {}
    transcript_lines: List[str] = []
    capture_transcript = False

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if capture_transcript:
            transcript_lines.append(raw_line)
            continue

        if ":" not in raw_line:
            continue

        key, value = raw_line.split(":", 1)
        key = key.strip().upper()
        value = value.strip()

        if key == "TRANSCRIPT_TEXT":
            if value:
                transcript_lines.append(value)
            capture_transcript = True
            continue

        metadata[key] = value

    transcript = TranscriptObject(
        evidence_id=metadata.get("EVIDENCE_ID", ""),
        transcript_status=metadata.get("TRANSCRIPT_STATUS", ""),
        transcript_text="\n".join(transcript_lines).strip(),
        source=metadata.get("SOURCE", str(path)),
        generated_by=metadata.get("GENERATED_BY", ""),
        verification_notes=metadata.get("VERIFICATION_NOTES", ""),
    )
    validate_transcript_object(transcript)
    return transcript


def validate_status_transition(current_status: str, target_status: str) -> None:
    expected_target = STATUS_TRANSITIONS.get(current_status)
    if expected_target != target_status:
        raise ValueError(
            f"Invalid evidence status transition: {current_status} -> {target_status}"
        )


def _require_transcribed_transcript(
    evidence: EvidenceObject,
    transcript: Optional[TranscriptObject],
) -> TranscriptObject:
    if transcript is None:
        raise ValueError(
            f"{evidence.evidence_id}: transcript_found requires a transcript artifact"
        )

    validate_transcript_object(transcript)
    if transcript.evidence_id != evidence.evidence_id:
        raise ValueError(
            f"{evidence.evidence_id}: transcript evidence_id mismatch: "
            f"{transcript.evidence_id}"
        )

    if transcript.transcript_status != "transcribed":
        raise ValueError(
            f"{evidence.evidence_id}: transcript_found requires "
            "transcript_status=transcribed"
        )

    return transcript


def _validate_immutable_fields(before: EvidenceObject, after: EvidenceObject) -> None:
    before_data = before.to_dict()
    after_data = after.to_dict()
    for field_name in IMMUTABLE_EVIDENCE_FIELDS:
        if before_data[field_name] != after_data[field_name]:
            raise ValueError(f"EvidenceObject.{field_name} cannot change during ingestion")


def upgrade_evidence_status(
    evidence: Any,
    target_status: str,
    transcript: Optional[TranscriptObject] = None,
    timestamp_start: Optional[str] = None,
    timestamp_end: Optional[str] = None,
    raw_quote: Optional[str] = None,
) -> EvidenceObject:
    current = coerce_evidence_object(evidence)
    validate_status_transition(current.verification_status, target_status)

    data = current.to_dict()
    data["verification_status"] = target_status

    if target_status == "transcript_found":
        transcript = _require_transcribed_transcript(current, transcript)
        data["transcript_status"] = transcript.transcript_status
    elif target_status == "timestamp_verified":
        data["timestamp_start"] = timestamp_start
        data["timestamp_end"] = timestamp_end
    elif target_status == "quote_verified":
        data["raw_quote"] = raw_quote

    upgraded = evidence_object_from_dict(data)
    _validate_immutable_fields(current, upgraded)
    validate_evidence_object(upgraded)
    return upgraded


def inspect_evidence_sources(
    index_path: Path = DEFAULT_INDEX_PATH,
    transcript_dir: Path = DEFAULT_TRANSCRIPT_DIR,
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for evidence in load_evidence_objects(index_path):
        transcript = load_transcript_artifact(evidence.evidence_id, transcript_dir)
        transcript_status = transcript.transcript_status if transcript else "missing"
        source_ready = evidence.verification_status == "source_found"
        upgrade_ready = transcript_status == "transcribed"
        records.append(
            {
                "evidence_id": evidence.evidence_id,
                "title": evidence.title,
                "url": evidence.url,
                "verification_status": evidence.verification_status,
                "transcript_status": transcript_status,
                "source_ready": source_ready,
                "upgrade_ready": upgrade_ready,
            }
        )
    return records
