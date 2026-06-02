#!/usr/bin/env python3
"""
Transcript Localization Engine v2.

Localizes transcript/caption segments only for harvested audio or video sources.
Dry-run creates no segments. This lane does not invent transcript text,
timestamps, quotes, claims, approvals, or contradictions.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json
import re
import shutil
import subprocess
import tempfile


DEFAULT_HARVESTED_SOURCES = Path("outputs/source_harvester_engine/harvested_sources.json")
DEFAULT_HARVESTER_SUMMARY = Path("outputs/source_harvester_engine/source_harvester_summary.json")

DEFAULT_OUTPUT_DIR = Path("outputs/transcript_localization_engine")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "transcript_localization_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "transcript_localization_summary.json"
SEGMENTS_OUTPUT = DEFAULT_OUTPUT_DIR / "localized_transcript_segments.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "transcript_localization_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "transcript_localization_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "transcript_localization_schema.json"

SCHEMA_VERSION = "transcript_localization_engine_v2"
DRY_RUN_STATUS = "TRANSCRIPT_LOCALIZATION_DRY_RUN_REFUSED"
CANDIDATE_STATUS = "TRANSCRIPT_LOCALIZATION_CANDIDATE"
PARTIAL_STATUS = "TRANSCRIPT_LOCALIZATION_PARTIAL"
REFUSED_STATUS = "TRANSCRIPT_LOCALIZATION_REFUSED"

UPSTREAM_STATUSES = (
    "SOURCE_HARVESTER_DRY_RUN_REFUSED",
    "SOURCE_HARVESTER_CANDIDATE",
    "SOURCE_HARVESTER_PARTIAL",
    "SOURCE_HARVESTER_REFUSED",
)

SEGMENT_VERIFICATION_STATUS = "CANDIDATE_TRANSCRIPT_SEGMENT_REQUIRES_MANUAL_REVIEW"
LOCALIZATION_STATUS = "localized_transcript_candidate"

HARVESTED_SOURCE_FIELDS = (
    "harvested_source_id",
    "registry_source_id",
    "source_name",
    "source_category",
    "platform",
    "content_url",
    "content_title",
    "content_owner",
    "published_date",
    "duration",
    "source_type",
    "metadata_method",
    "metadata_hash",
    "harvest_status",
    "manual_review_required",
    "harvested_source_root",
)

SEGMENT_FIELDS = (
    "segment_id",
    "harvested_source_id",
    "content_url",
    "content_title",
    "speaker_name",
    "transcript_text",
    "timestamp_start",
    "timestamp_end",
    "transcript_line_start",
    "transcript_line_end",
    "source_method",
    "segment_hash",
    "segment_root",
    "verification_status",
    "manual_review_required",
)

REFUSAL_FIELDS = (
    "refusal_id",
    "harvested_source_id",
    "content_url",
    "content_title",
    "source_type",
    "refusal_code",
    "refusal_reason",
    "manual_review_required",
    "refusal_root",
)

REFUSAL_CODES = (
    "REFUSED_NO_HARVESTED_SOURCES",
    "REFUSED_NOT_AUDIO_VIDEO",
    "REFUSED_TRANSCRIPT_TOOL_UNAVAILABLE",
    "REFUSED_NO_TRANSCRIPT_AVAILABLE",
    "REFUSED_TRANSCRIPT_METADATA_UNVERIFIED",
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_json(payload: Dict[str, Any]) -> str:
    return _sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string")


def _closed_flags(data: Dict[str, Any]) -> bool:
    return (
        data.get("production_ready") is False
        and data.get("approved_evidence") == 0
        and data.get("public_ready") is False
        and data.get("institutional_ready") is False
    )


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "transcript_localization_only": True,
        "upstream_statuses": list(UPSTREAM_STATUSES),
        "harvested_source_fields": list(HARVESTED_SOURCE_FIELDS),
        "localized_segment_fields": list(SEGMENT_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "dry_run_behavior": "Dry-run creates no transcript segments and refuses no empty upstream.",
        "localize_behavior": (
            "Localize attempts transcript extraction only for harvested audio/video sources "
            "using yt-dlp subtitle files. It must not invent transcript text or timestamps."
        ),
        "segment_requirements": {
            "transcript_text": "non-empty",
            "timestamp_or_line_anchor": "timestamp_start/timestamp_end or line range required",
            "manual_review_required": True,
        },
        "prohibited_outputs": {
            "quotes_created": 0,
            "timestamps_invented": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "evidence_approved_count": 0,
        },
        "root_rules": {
            "segment_hash": "sha256 over transcript text and localization anchors",
            "segment_root": "sha256 over localized segment excluding segment_root",
            "refusal_root": "sha256 over refusal content excluding refusal_root",
            "transcript_localization_root": (
                "sha256 over sorted segment roots, sorted refusal roots, and closed flags"
            ),
        },
        "closed_governance_flags": {
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        },
    }


def validate_schema(schema: Dict[str, Any]) -> None:
    if schema.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("transcript_localization_schema schema_version changed unexpectedly")
    if schema.get("localized_segment_fields") != list(SEGMENT_FIELDS):
        raise ValueError("transcript_localization_schema segment fields changed")
    if schema.get("refusal_fields") != list(REFUSAL_FIELDS):
        raise ValueError("transcript_localization_schema refusal fields changed")


def validate_harvested_source(source: Dict[str, Any]) -> None:
    if set(source.keys()) != set(HARVESTED_SOURCE_FIELDS):
        raise ValueError("Harvested source fields changed unexpectedly")
    for field_name in (
        "harvested_source_id",
        "registry_source_id",
        "source_name",
        "source_category",
        "platform",
        "content_url",
        "content_title",
        "content_owner",
        "published_date",
        "duration",
        "source_type",
        "metadata_method",
        "metadata_hash",
        "harvest_status",
        "harvested_source_root",
    ):
        _require_nonempty_string(source, field_name, "HarvestedSource")
    if source["manual_review_required"] is not True:
        raise ValueError("HarvestedSource.manual_review_required must remain true")
    if not _is_nonzero_hash(source["metadata_hash"]):
        raise ValueError("HarvestedSource.metadata_hash must be non-zero")
    if not _is_nonzero_hash(source["harvested_source_root"]):
        raise ValueError("HarvestedSource.harvested_source_root must be non-zero")


def _validate_upstream(
    harvested_payload: Dict[str, Any],
    harvester_summary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not harvested_payload:
        raise ValueError("harvested_sources.json is missing")
    if not harvester_summary:
        raise ValueError("source_harvester_summary.json is missing")
    if harvester_summary.get("source_harvester_status") not in UPSTREAM_STATUSES:
        raise ValueError("Source harvester upstream status is invalid")
    if harvester_summary.get("source_harvester_schema_ready") is not True:
        raise ValueError("Source harvester schema is not ready")
    for counter in (
        "quotes_created",
        "timestamps_created",
        "transcripts_created",
        "claims_created",
        "contradictions_created",
    ):
        if harvester_summary.get(counter) != 0:
            raise ValueError(f"Source harvester must not create {counter}")
    if not _closed_flags(harvester_summary):
        raise ValueError("Source harvester guardrails must remain closed")
    sources = harvested_payload.get("harvested_sources")
    if not isinstance(sources, list):
        raise ValueError("harvested_sources must be a list")
    if len(sources) != harvester_summary.get("harvested_source_count"):
        raise ValueError("harvested_sources count does not match summary")
    for source in sources:
        validate_harvested_source(source)
    return sources


def _segment_hash_material(segment: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "harvested_source_id": segment["harvested_source_id"],
        "content_url": segment["content_url"],
        "transcript_text": segment["transcript_text"],
        "timestamp_start": segment["timestamp_start"],
        "timestamp_end": segment["timestamp_end"],
        "transcript_line_start": segment["transcript_line_start"],
        "transcript_line_end": segment["transcript_line_end"],
        "source_method": segment["source_method"],
    }


def _segment_root_material(segment: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(segment)
    material.pop("segment_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _make_refusal(source: Dict[str, Any], code: str, reason: str) -> Dict[str, Any]:
    refusal = {
        "refusal_id": f"TRANSCRIPT_REFUSAL_{source.get('harvested_source_id', 'NO_HARVESTED_SOURCE')}",
        "harvested_source_id": source.get("harvested_source_id", ""),
        "content_url": source.get("content_url", "UNSPECIFIED"),
        "content_title": source.get("content_title", "UNSPECIFIED"),
        "source_type": source.get("source_type", "UNSPECIFIED"),
        "refusal_code": code,
        "refusal_reason": reason,
        "manual_review_required": True,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def _make_segment(
    source: Dict[str, Any],
    index: int,
    text: str,
    timestamp_start: str,
    timestamp_end: str,
    source_method: str,
) -> Dict[str, Any]:
    segment = {
        "segment_id": f"SEGMENT_{source['harvested_source_id']}_{index:04d}",
        "harvested_source_id": source["harvested_source_id"],
        "content_url": source["content_url"],
        "content_title": source["content_title"],
        "speaker_name": "Duma Boko",
        "transcript_text": text.strip(),
        "timestamp_start": timestamp_start,
        "timestamp_end": timestamp_end,
        "transcript_line_start": index,
        "transcript_line_end": index,
        "source_method": source_method,
        "segment_hash": "",
        "segment_root": "",
        "verification_status": SEGMENT_VERIFICATION_STATUS,
        "manual_review_required": True,
    }
    segment["segment_hash"] = _hash_json(_segment_hash_material(segment))
    segment["segment_root"] = _hash_json(_segment_root_material(segment))
    return segment


def _clean_transcript_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_vtt(path: Path, source: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(
        r"(?P<start>\d\d:\d\d:\d\d\.\d+|\d\d:\d\d\.\d+)\s+-->\s+"
        r"(?P<end>\d\d:\d\d:\d\d\.\d+|\d\d:\d\d\.\d+).*?\n(?P<text>.*?)(?=\n\n|\Z)",
        re.DOTALL,
    )
    segments: List[Dict[str, Any]] = []
    for index, match in enumerate(pattern.finditer(raw), start=1):
        text = _clean_transcript_text(match.group("text"))
        if not text:
            continue
        segments.append(
            _make_segment(
                source,
                index,
                text,
                match.group("start"),
                match.group("end"),
                "yt_dlp_subtitle_vtt",
            )
        )
    return segments


def _localize_source(
    source: Dict[str, Any],
    mode: str,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    validate_harvested_source(source)
    if mode == "dry-run":
        return [], _make_refusal(
            source,
            "REFUSED_NO_TRANSCRIPT_AVAILABLE",
            "Dry-run does not attempt transcript localization.",
        )
    if source["source_type"] not in ("audio", "video"):
        return [], _make_refusal(
            source,
            "REFUSED_NOT_AUDIO_VIDEO",
            "Transcript localization only supports harvested audio or video sources.",
        )
    if shutil.which("yt-dlp") is None:
        return [], _make_refusal(
            source,
            "REFUSED_TRANSCRIPT_TOOL_UNAVAILABLE",
            "yt-dlp is not installed for transcript localization.",
        )
    with tempfile.TemporaryDirectory() as tmpdir:
        output_template = str(Path(tmpdir) / "%(id)s.%(ext)s")
        command = [
            "yt-dlp",
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-format",
            "vtt",
            "--sub-langs",
            "en.*",
            "-o",
            output_template,
            source["content_url"],
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return [], _make_refusal(source, "REFUSED_NO_TRANSCRIPT_AVAILABLE", str(exc))
        if completed.returncode != 0:
            return [], _make_refusal(
                source,
                "REFUSED_NO_TRANSCRIPT_AVAILABLE",
                completed.stderr.strip() or "yt-dlp did not produce subtitles.",
            )
        segments: List[Dict[str, Any]] = []
        for subtitle_path in sorted(Path(tmpdir).glob("*.vtt")):
            segments.extend(_parse_vtt(subtitle_path, source))
        if not segments:
            return [], _make_refusal(
                source,
                "REFUSED_TRANSCRIPT_METADATA_UNVERIFIED",
                "Subtitle files were unavailable or contained no localized transcript text.",
            )
        return segments, None


def validate_segment(segment: Dict[str, Any]) -> None:
    if set(segment.keys()) != set(SEGMENT_FIELDS):
        raise ValueError("Localized transcript segment fields changed unexpectedly")
    for field_name in (
        "segment_id",
        "harvested_source_id",
        "content_url",
        "content_title",
        "speaker_name",
        "transcript_text",
        "timestamp_start",
        "timestamp_end",
        "source_method",
        "segment_hash",
        "segment_root",
        "verification_status",
    ):
        _require_nonempty_string(segment, field_name, "LocalizedTranscriptSegment")
    if segment["speaker_name"] != "Duma Boko":
        raise ValueError("LocalizedTranscriptSegment.speaker_name must remain Duma Boko")
    if segment["transcript_line_start"] <= 0 or segment["transcript_line_end"] <= 0:
        raise ValueError("LocalizedTranscriptSegment line anchors must be positive")
    if segment["manual_review_required"] is not True:
        raise ValueError("LocalizedTranscriptSegment.manual_review_required must remain true")
    if segment["verification_status"] != SEGMENT_VERIFICATION_STATUS:
        raise ValueError("LocalizedTranscriptSegment.verification_status changed")
    if segment["segment_hash"] != _hash_json(_segment_hash_material(segment)):
        raise ValueError(f"segment_hash mismatch for {segment['segment_id']}")
    if segment["segment_root"] != _hash_json(_segment_root_material(segment)):
        raise ValueError(f"segment_root mismatch for {segment['segment_id']}")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Transcript localization refusal fields changed unexpectedly")
    for field_name in (
        "refusal_id",
        "content_url",
        "content_title",
        "source_type",
        "refusal_code",
        "refusal_reason",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "TranscriptLocalizationRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}")
    if refusal["manual_review_required"] is not True:
        raise ValueError("TranscriptLocalizationRefusal.manual_review_required must remain true")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}")


def _status_for(mode: str, segment_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if segment_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if segment_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _build_report(
    status: str,
    mode: str,
    segments: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    transcript_localization_root: str,
) -> str:
    segment_lines = ["- None"]
    if segments:
        segment_lines = []
        for segment in segments:
            segment_lines.extend(
                [
                    f"- {segment['segment_id']}",
                    f"  - Source: {segment['content_title']}",
                    f"  - Timestamp: {segment['timestamp_start']} to {segment['timestamp_end']}",
                    f"  - Manual Review Required: {segment['manual_review_required']}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Source: {refusal['content_title']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    lines = [
        "# Transcript Localization Engine v2",
        "",
        "This lane localizes real transcript segments only when transcript text and "
        "timestamps are available from supported tools. It does not invent text, "
        "timestamps, quotes, claims, approvals, or contradictions.",
        "",
        "## Summary",
        f"- transcript_localization_status: {status}",
        f"- mode: {mode}",
        f"- localized_segment_count: {len(segments)}",
        f"- refusal_count: {len(refusals)}",
        f"- transcript_localization_root: {transcript_localization_root}",
        "",
        "## Localized Transcript Segments",
        *segment_lines,
        "",
        "## Refusals",
        *refusal_lines,
        "",
        "## Guardrails",
        "- Quotes Created: 0",
        "- Timestamps Invented: 0",
        "- Claims Created: 0",
        "- Contradictions Created: 0",
        "- Evidence Approved Count: 0",
        "- Production Ready: False",
        "- Approved Evidence: 0",
        "- Public Ready: False",
        "- Institutional Ready: False",
        "",
    ]
    return "\n".join(lines)


def build_transcript_localization_engine(
    mode: str = "dry-run",
    harvested_sources_path: Path = DEFAULT_HARVESTED_SOURCES,
    harvester_summary_path: Path = DEFAULT_HARVESTER_SUMMARY,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "localize"):
        raise ValueError("mode must be dry-run or localize")

    harvested_payload = _load_json(harvested_sources_path)
    harvester_summary = _load_json(harvester_summary_path)
    harvested_sources = _validate_upstream(harvested_payload, harvester_summary)
    schema = _schema()
    validate_schema(schema)

    segments: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    if harvested_sources:
        for harvested_source in harvested_sources:
            source_segments, refusal = _localize_source(harvested_source, mode)
            for segment in source_segments:
                validate_segment(segment)
                segments.append(segment)
            if refusal is not None:
                validate_refusal(refusal)
                refusals.append(refusal)

    segment_roots = [segment["segment_root"] for segment in segments]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    transcript_localization_root = _hash_json(
        {
            "segment_roots": sorted(segment_roots),
            "refusal_roots": sorted(refusal_roots),
            "quotes_created": 0,
            "timestamps_invented": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        }
    )
    status = _status_for(mode, len(segments), len(refusals))
    schema_hash = _hash_json(schema)
    report = _build_report(status, mode, segments, refusals, transcript_localization_root)
    report_hash = _sha256_text(report)
    summary = {
        "transcript_localization_status": status,
        "mode": mode,
        "harvested_source_count": len(harvested_sources),
        "localized_segment_count": len(segments),
        "refusal_count": len(refusals),
        "transcript_localization_schema_ready": True,
        "transcript_localization_ready": True,
        "quotes_created": 0,
        "timestamps_invented": 0,
        "claims_created": 0,
        "contradictions_created": 0,
        "evidence_approved_count": 0,
        "segment_roots": segment_roots,
        "refusal_roots": refusal_roots,
        "transcript_localization_schema_hash": schema_hash,
        "transcript_localization_report_hash": report_hash,
        "transcript_localization_root": transcript_localization_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    if mode == "dry-run" and len(harvested_sources) == 0 and len(refusals) != 0:
        raise ValueError("Empty dry-run upstream should not fabricate refusals")
    if not _closed_flags(summary):
        raise ValueError("Transcript localization summary guardrails must remain closed")

    status_payload = {
        "records": [
            {
                "transcript_localization_status": status,
                "harvested_source_count": len(harvested_sources),
                "localized_segment_count": len(segments),
                "refusal_count": len(refusals),
                "transcript_localization_root": transcript_localization_root,
                "production_ready": False,
                "approved_evidence": 0,
                "public_ready": False,
                "institutional_ready": False,
            }
        ]
    }

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(STATUS_OUTPUT, status_payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(SEGMENTS_OUTPUT, {"localized_transcript_segments": segments})
    _write_json(REFUSALS_OUTPUT, {"transcript_localization_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "payload": status_payload,
        "summary": summary,
        "localized_transcript_segments": segments,
        "transcript_localization_refusals": refusals,
        "schema": schema,
        "report": report,
    }
