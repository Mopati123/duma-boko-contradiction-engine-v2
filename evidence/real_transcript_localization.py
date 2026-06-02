#!/usr/bin/env python3
"""
Real Transcript Localization v2.

Localizes real transcript or page-text segments from harvested sources. This
lane never invents transcript text, timestamps, quotes, claims, contradictions,
production readiness, or approved evidence.
"""

from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request


DEFAULT_HARVESTED_SOURCES = Path("outputs/source_harvester_engine/harvested_sources.json")
DEFAULT_HARVESTER_SUMMARY = Path("outputs/source_harvester_engine/source_harvester_summary.json")

DEFAULT_OUTPUT_DIR = Path("outputs/real_transcript_localization")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "real_transcript_localization_summary.json"
SEGMENTS_OUTPUT = DEFAULT_OUTPUT_DIR / "localized_transcript_segments.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "transcript_localization_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "real_transcript_localization_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "real_transcript_localization_schema.json"

SCHEMA_VERSION = "real_transcript_localization_v2"

DRY_RUN_STATUS = "REAL_TRANSCRIPT_LOCALIZATION_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "REAL_TRANSCRIPT_LOCALIZATION_CANDIDATE"
PARTIAL_STATUS = "REAL_TRANSCRIPT_LOCALIZATION_PARTIAL"
REFUSED_STATUS = "REAL_TRANSCRIPT_LOCALIZATION_REFUSED"

UPSTREAM_STATUSES = (
    "SOURCE_HARVESTER_CANDIDATE",
    "SOURCE_HARVESTER_PARTIAL",
    "SOURCE_HARVESTER_REFUSED",
)

SEGMENT_VERIFICATION_STATUS = "REAL_LOCALIZED_TEXT_REQUIRES_MANUAL_REVIEW"
UNAVAILABLE = "UNAVAILABLE"

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
    "localized_segment_id",
    "harvested_source_id",
    "registry_source_id",
    "content_url",
    "content_title",
    "source_type",
    "source_method",
    "localized_text",
    "timestamp_start",
    "timestamp_end",
    "text_line_start",
    "text_line_end",
    "text_char_start",
    "text_char_end",
    "verification_status",
    "manual_review_required",
    "metadata_hash",
    "localized_segment_root",
)

REFUSAL_FIELDS = (
    "refusal_id",
    "harvested_source_id",
    "registry_source_id",
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
    "REFUSED_DRY_RUN_VALIDATION_ONLY",
    "REFUSED_TRANSCRIPT_TOOL_UNAVAILABLE",
    "REFUSED_NO_CAPTIONS_AVAILABLE",
    "REFUSED_TEXT_FETCH_FAILED",
    "REFUSED_UNSUPPORTED_CONTENT_TYPE",
    "REFUSED_NO_LOCALIZABLE_TEXT",
    "REFUSED_TEXT_METADATA_UNVERIFIED",
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


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string")


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _is_public_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


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
        "real_transcript_localization_only": True,
        "upstream_statuses": list(UPSTREAM_STATUSES),
        "harvested_source_fields": list(HARVESTED_SOURCE_FIELDS),
        "localized_segment_fields": list(SEGMENT_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "modes": ["dry-run", "localize"],
        "localization_methods": [
            "yt_dlp_subtitle_vtt",
            "html_body_text_extraction",
        ],
        "prohibited_outputs": {
            "transcripts_invented": 0,
            "timestamps_invented": 0,
            "quotes_created": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "evidence_approved_count": 0,
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
        raise ValueError("real_transcript_localization schema_version changed")
    if schema.get("localized_segment_fields") != list(SEGMENT_FIELDS):
        raise ValueError("real_transcript_localization segment fields changed")
    if schema.get("refusal_fields") != list(REFUSAL_FIELDS):
        raise ValueError("real_transcript_localization refusal fields changed")


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
    if not _is_public_url(source["content_url"]):
        raise ValueError("HarvestedSource.content_url must be public HTTP(S)")
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
        "source_method": segment["source_method"],
        "localized_text": segment["localized_text"],
        "timestamp_start": segment["timestamp_start"],
        "timestamp_end": segment["timestamp_end"],
        "text_line_start": segment["text_line_start"],
        "text_line_end": segment["text_line_end"],
        "text_char_start": segment["text_char_start"],
        "text_char_end": segment["text_char_end"],
    }


def _segment_root_material(segment: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(segment)
    material.pop("localized_segment_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _make_refusal(source: Dict[str, Any], code: str, reason: str) -> Dict[str, Any]:
    refusal = {
        "refusal_id": f"REAL_TRANSCRIPT_REFUSAL_{source.get('harvested_source_id', 'NO_SOURCE')}",
        "harvested_source_id": source.get("harvested_source_id", "NO_HARVESTED_SOURCE"),
        "registry_source_id": source.get("registry_source_id", "NO_REGISTRY_SOURCE"),
        "content_url": source.get("content_url", UNAVAILABLE),
        "content_title": source.get("content_title", UNAVAILABLE),
        "source_type": source.get("source_type", UNAVAILABLE),
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
    localized_text: str,
    source_method: str,
    timestamp_start: Optional[str],
    timestamp_end: Optional[str],
    line_start: int,
    line_end: int,
    char_start: int,
    char_end: int,
) -> Dict[str, Any]:
    segment = {
        "localized_segment_id": f"REAL_SEGMENT_{source['harvested_source_id']}_{index:04d}",
        "harvested_source_id": source["harvested_source_id"],
        "registry_source_id": source["registry_source_id"],
        "content_url": source["content_url"],
        "content_title": source["content_title"],
        "source_type": source["source_type"],
        "source_method": source_method,
        "localized_text": localized_text.strip(),
        "timestamp_start": timestamp_start,
        "timestamp_end": timestamp_end,
        "text_line_start": int(line_start),
        "text_line_end": int(line_end),
        "text_char_start": int(char_start),
        "text_char_end": int(char_end),
        "verification_status": SEGMENT_VERIFICATION_STATUS,
        "manual_review_required": True,
        "metadata_hash": "",
        "localized_segment_root": "",
    }
    segment["metadata_hash"] = _hash_json(_segment_hash_material(segment))
    segment["localized_segment_root"] = _hash_json(_segment_root_material(segment))
    return segment


def _clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
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
        text = _clean_text(match.group("text"))
        if len(text) < 20:
            continue
        segments.append(
            _make_segment(
                source,
                index,
                text,
                "yt_dlp_subtitle_vtt",
                match.group("start"),
                match.group("end"),
                index,
                index,
                0,
                len(text),
            )
        )
    return segments


class _BodyTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._in_body = False
        self.parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        lowered = tag.lower()
        if lowered == "body":
            self._in_body = True
        if lowered in ("script", "style", "noscript", "svg", "nav", "footer", "form"):
            self._skip_depth += 1
        if lowered in ("p", "div", "section", "article", "li", "h1", "h2", "h3", "br"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in ("script", "style", "noscript", "svg", "nav", "footer", "form") and self._skip_depth:
            self._skip_depth -= 1
        if lowered == "body":
            self._in_body = False
        if lowered in ("p", "div", "section", "article", "li", "h1", "h2", "h3"):
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if not self._in_body and self.parts:
            return
        stripped = data.strip()
        if stripped:
            self.parts.append(stripped)


def _fetch_html(url: str) -> Tuple[str, str, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; RealTranscriptLocalization/2.0)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return "", content_type, "Unsupported content-type for text localization."
            return response.read(900000).decode("utf-8", errors="replace"), content_type, ""
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return "", "", f"Unable to fetch source text: {exc}"


def _extract_body_lines(page_text: str) -> List[str]:
    parser = _BodyTextParser()
    parser.feed(page_text)
    raw = "\n".join(parser.parts)
    lines: List[str] = []
    seen = set()
    for line in raw.splitlines():
        cleaned = _clean_text(line)
        if len(cleaned) < 25:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        lines.append(cleaned)
    return lines


def _segments_from_lines(source: Dict[str, Any], lines: List[str]) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    char_cursor = 0
    for line_number, line in enumerate(lines, start=1):
        text = line.strip()
        if not text:
            continue
        if len(text) > 1500:
            text = text[:1500].rsplit(" ", 1)[0].strip()
        char_start = char_cursor
        char_end = char_start + len(text)
        segments.append(
            _make_segment(
                source,
                len(segments) + 1,
                text,
                "html_body_text_extraction",
                None,
                None,
                line_number,
                line_number,
                char_start,
                char_end,
            )
        )
        char_cursor = char_end + 1
        if len(segments) >= 25:
            break
    return segments


def _localize_with_ytdlp(source: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if shutil.which("yt-dlp") is None:
        return [], _make_refusal(
            source,
            "REFUSED_TRANSCRIPT_TOOL_UNAVAILABLE",
            "yt-dlp is not installed for caption localization.",
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
            return [], _make_refusal(source, "REFUSED_NO_CAPTIONS_AVAILABLE", str(exc))
        if completed.returncode != 0:
            return [], _make_refusal(
                source,
                "REFUSED_NO_CAPTIONS_AVAILABLE",
                completed.stderr.strip() or "yt-dlp did not produce subtitles.",
            )
        segments: List[Dict[str, Any]] = []
        for subtitle_path in sorted(Path(tmpdir).glob("*.vtt")):
            segments.extend(_parse_vtt(subtitle_path, source))
        if not segments:
            return [], _make_refusal(
                source,
                "REFUSED_TEXT_METADATA_UNVERIFIED",
                "Subtitle files were unavailable or contained no localized transcript text.",
            )
        return segments, None


def _localize_html_text(source: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    page_text, content_type, error = _fetch_html(source["content_url"])
    if error:
        code = "REFUSED_UNSUPPORTED_CONTENT_TYPE" if content_type else "REFUSED_TEXT_FETCH_FAILED"
        return [], _make_refusal(source, code, error)
    lines = _extract_body_lines(page_text)
    if not lines:
        return [], _make_refusal(
            source,
            "REFUSED_NO_LOCALIZABLE_TEXT",
            "Fetched HTML contained no extractable body text.",
        )
    segments = _segments_from_lines(source, lines)
    if not segments:
        return [], _make_refusal(
            source,
            "REFUSED_TEXT_METADATA_UNVERIFIED",
            "Body text extraction produced no valid localized segments.",
        )
    return segments, None


def _localize_source(source: Dict[str, Any], mode: str) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    validate_harvested_source(source)
    if mode == "dry-run":
        return [], None
    if source["source_type"] in ("audio", "video") and "youtube.com" in source["content_url"]:
        segments, refusal = _localize_with_ytdlp(source)
        if segments:
            return segments, None
        # Fall through to HTML extraction only when the URL itself is an HTML page.
        if refusal and "youtube.com" in source["content_url"]:
            return [], refusal
    return _localize_html_text(source)


def validate_segment(segment: Dict[str, Any]) -> None:
    if set(segment.keys()) != set(SEGMENT_FIELDS):
        raise ValueError("Real localized segment fields changed unexpectedly")
    for field_name in (
        "localized_segment_id",
        "harvested_source_id",
        "registry_source_id",
        "content_url",
        "content_title",
        "source_type",
        "source_method",
        "localized_text",
        "verification_status",
        "metadata_hash",
        "localized_segment_root",
    ):
        _require_nonempty_string(segment, field_name, "RealLocalizedTranscriptSegment")
    if segment["manual_review_required"] is not True:
        raise ValueError("RealLocalizedTranscriptSegment.manual_review_required must remain true")
    if segment["verification_status"] != SEGMENT_VERIFICATION_STATUS:
        raise ValueError("RealLocalizedTranscriptSegment.verification_status changed")
    if segment["timestamp_start"] is not None and not isinstance(segment["timestamp_start"], str):
        raise ValueError("RealLocalizedTranscriptSegment.timestamp_start must be string or null")
    if segment["timestamp_end"] is not None and not isinstance(segment["timestamp_end"], str):
        raise ValueError("RealLocalizedTranscriptSegment.timestamp_end must be string or null")
    for field_name in ("text_line_start", "text_line_end", "text_char_start", "text_char_end"):
        if not isinstance(segment[field_name], int) or segment[field_name] < 0:
            raise ValueError(f"RealLocalizedTranscriptSegment.{field_name} must be a non-negative integer")
    if segment["metadata_hash"] != _hash_json(_segment_hash_material(segment)):
        raise ValueError(f"metadata_hash mismatch for {segment['localized_segment_id']}")
    if segment["localized_segment_root"] != _hash_json(_segment_root_material(segment)):
        raise ValueError(f"localized_segment_root mismatch for {segment['localized_segment_id']}")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Real transcript localization refusal fields changed unexpectedly")
    for field_name in (
        "refusal_id",
        "harvested_source_id",
        "registry_source_id",
        "content_url",
        "content_title",
        "source_type",
        "refusal_code",
        "refusal_reason",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "RealTranscriptLocalizationRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}")
    if refusal["manual_review_required"] is not True:
        raise ValueError("RealTranscriptLocalizationRefusal.manual_review_required must remain true")
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
    harvested_source_count: int,
    segments: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    segment_lines = ["- None"]
    if segments:
        segment_lines = []
        for segment in segments[:20]:
            text_preview = segment["localized_text"][:140].replace("\n", " ")
            segment_lines.extend(
                [
                    f"- {segment['localized_segment_id']}",
                    f"  - Source: {segment['content_title']}",
                    f"  - Method: {segment['source_method']}",
                    f"  - Text Preview: {text_preview}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Source: {refusal['content_title']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Real Transcript Localization v2",
            "",
            "This lane localizes only real transcript or source text from harvested "
            "sources. It does not invent transcript text, timestamps, quotes, claims, "
            "contradictions, production readiness, or approved evidence.",
            "",
            "## Summary",
            f"- real_transcript_localization_status: {status}",
            f"- mode: {mode}",
            f"- harvested_source_count: {harvested_source_count}",
            f"- localized_segment_count: {len(segments)}",
            f"- refusal_count: {len(refusals)}",
            f"- real_transcript_localization_root: {root}",
            "",
            "## Localized Segments",
            *segment_lines,
            "",
            "## Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- Transcripts Invented: 0",
            "- Timestamps Invented: 0",
            "- Quotes Created: 0",
            "- Claims Created: 0",
            "- Contradictions Created: 0",
            "- Evidence Approved Count: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "- Public Ready: False",
            "- Institutional Ready: False",
            "",
        ]
    )


def build_real_transcript_localization(
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
    if not harvested_sources and mode == "localize":
        refusal = _make_refusal(
            {},
            "REFUSED_NO_HARVESTED_SOURCES",
            "No harvested sources were available for localization.",
        )
        validate_refusal(refusal)
        refusals.append(refusal)
    for harvested_source in harvested_sources:
        source_segments, refusal = _localize_source(harvested_source, mode)
        for segment in source_segments:
            validate_segment(segment)
            segments.append(segment)
        if refusal is not None:
            validate_refusal(refusal)
            refusals.append(refusal)

    segment_roots = [segment["localized_segment_root"] for segment in segments]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    root = _hash_json(
        {
            "localized_segment_roots": sorted(segment_roots),
            "refusal_roots": sorted(refusal_roots),
            "transcripts_invented": 0,
            "timestamps_invented": 0,
            "quotes_created": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        }
    )
    status = _status_for(mode, len(segments), len(refusals))
    report = _build_report(status, mode, len(harvested_sources), segments, refusals, root)
    summary = {
        "real_transcript_localization_status": status,
        "mode": mode,
        "harvested_source_count": len(harvested_sources),
        "localized_segment_count": len(segments),
        "refusal_count": len(refusals),
        "transcripts_invented": 0,
        "timestamps_invented": 0,
        "quotes_created": 0,
        "claims_created": 0,
        "contradictions_created": 0,
        "evidence_approved_count": 0,
        "localized_segment_roots": segment_roots,
        "refusal_roots": refusal_roots,
        "real_transcript_localization_schema_hash": _hash_json(schema),
        "real_transcript_localization_report_hash": _sha256_text(report),
        "real_transcript_localization_root": root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    if mode == "dry-run" and (segments or refusals):
        raise ValueError("Dry-run must validate harvested sources only")
    for counter_name in (
        "transcripts_invented",
        "timestamps_invented",
        "quotes_created",
        "claims_created",
        "contradictions_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0")
    if not _closed_flags(summary):
        raise ValueError("Real transcript localization guardrails must remain closed")

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(SEGMENTS_OUTPUT, {"localized_transcript_segments": segments})
    _write_json(REFUSALS_OUTPUT, {"transcript_localization_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "summary": summary,
        "localized_transcript_segments": segments,
        "transcript_localization_refusals": refusals,
        "schema": schema,
        "report": report,
    }
