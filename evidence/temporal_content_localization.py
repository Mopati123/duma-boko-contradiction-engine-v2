#!/usr/bin/env python3
"""
Temporal Content Localization v2.

Localizes deterministic reviewable text segments from harvested temporal
sources. This lane extracts text only; it does not summarize, infer meaning,
create quotes, timestamps, claims, contradictions, embeddings, production
readiness, or approved evidence.
"""

from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse
import hashlib
import html
import http.client
import json
import re
import urllib.error
import urllib.request
import zlib


DEFAULT_HARVESTED_SOURCES = Path("outputs/temporal_source_harvester/harvested_temporal_sources.json")
DEFAULT_HARVESTER_SUMMARY = Path("outputs/temporal_source_harvester/temporal_source_harvester_summary.json")
DEFAULT_OUTPUT_DIR = Path("outputs/temporal_content_localization")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_content_localization_summary.json"
SEGMENTS_OUTPUT = DEFAULT_OUTPUT_DIR / "localized_temporal_segments.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_content_localization_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_content_localization_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "temporal_content_localization_schema.json"

SCHEMA_VERSION = "temporal_content_localization_v2"
UPSTREAM_SCHEMA_VERSION = "temporal_source_harvester_v2"
MAX_FETCH_BYTES = 2_000_000
MAX_SEGMENT_CHARS = 1000
UNAVAILABLE = "UNAVAILABLE"

DRY_RUN_STATUS = "TEMPORAL_CONTENT_LOCALIZATION_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "TEMPORAL_CONTENT_LOCALIZATION_CANDIDATE"
PARTIAL_STATUS = "TEMPORAL_CONTENT_LOCALIZATION_PARTIAL"
REFUSED_STATUS = "TEMPORAL_CONTENT_LOCALIZATION_REFUSED"

UPSTREAM_STATUSES = (
    "TEMPORAL_SOURCE_HARVESTER_CANDIDATE",
    "TEMPORAL_SOURCE_HARVESTER_PARTIAL",
    "TEMPORAL_SOURCE_HARVESTER_REFUSED",
)
TIME_DIRECTIONS = ("BEFORE", "AFTER")
SOURCE_TYPES = (
    "MANIFESTO",
    "RALLY_VIDEO",
    "INTERVIEW",
    "OFFICIAL_STATEMENT",
    "GOVERNMENT_UPDATE",
    "MINISTRY_UPDATE",
    "BUDGET_DOCUMENT",
    "PARLIAMENT_RECORD",
    "NEWS_FOLLOWUP",
    "PARTY_WEBSITE",
    "SOCIAL_MEDIA_POST",
)

HARVESTED_FIELDS = (
    "harvested_temporal_source_id",
    "source_id",
    "time_direction",
    "source_type",
    "url",
    "title",
    "publisher",
    "published_date",
    "topic",
    "http_status",
    "content_type",
    "content_length",
    "content_sha256",
    "text_excerpt",
    "harvest_method",
    "manual_review_required",
    "metadata_hash",
    "harvest_root",
)
SEGMENT_FIELDS = (
    "localized_segment_id",
    "harvested_temporal_source_id",
    "source_id",
    "time_direction",
    "source_type",
    "url",
    "segment_index",
    "segment_text",
    "segment_sha256",
    "publisher",
    "published_date",
    "topic",
    "manual_review_required",
    "localization_root",
)
REFUSAL_FIELDS = (
    "refusal_id",
    "source_id",
    "refusal_code",
    "refusal_reason",
    "manual_review_required",
    "refusal_root",
)
REFUSAL_CODES = (
    "REFUSED_MALFORMED_HARVESTED_SOURCE",
    "REFUSED_HARVESTED_METADATA_HASH_MISMATCH",
    "REFUSED_HARVEST_ROOT_MISMATCH",
    "REFUSED_UPSTREAM_GUARDRAIL_FAILURE",
    "REFUSED_DUPLICATE_HARVESTED_SOURCE_ID",
    "REFUSED_REFETCH_FAILED",
    "REFUSED_CONTENT_HASH_MISMATCH",
    "REFUSED_UNSUPPORTED_CONTENT_TYPE",
    "REFUSED_PDF_EXTRACTION_UNAVAILABLE",
    "REFUSED_NO_LOCALIZABLE_TEXT",
    "REFUSED_METADATA_UNVERIFIED",
)


class TemporalContentLocalizationRefusal(ValueError):
    def __init__(self, code: str, reason: str):
        super().__init__(reason)
        self.code = code
        self.reason = reason


class _VisibleBodyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._in_body = False
        self.parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        lowered = tag.lower()
        if lowered == "body":
            self._in_body = True
        if lowered in ("script", "style", "noscript", "svg", "nav", "footer", "form", "header"):
            self._skip_depth += 1
        if lowered in ("article", "section", "main", "p", "li", "div", "br", "h1", "h2", "h3", "h4"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in ("script", "style", "noscript", "svg", "nav", "footer", "form", "header") and self._skip_depth:
            self._skip_depth -= 1
        if lowered == "body":
            self._in_body = False
        if lowered in ("article", "section", "main", "p", "li", "div", "h1", "h2", "h3", "h4"):
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if not self._in_body and self.parts:
            return
        stripped = data.strip()
        if stripped:
            self.parts.append(stripped)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_json(payload: Any) -> str:
    return _sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


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


def _require_nonempty_string(data: Dict[str, Any], field_name: str, code: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise TemporalContentLocalizationRefusal(code, f"{field_name} must be a non-empty string.")


def _harvested_metadata_material(source: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: source[field]
        for field in HARVESTED_FIELDS
        if field not in ("metadata_hash", "harvest_root")
    }


def _harvest_root_material(source: Dict[str, Any]) -> Dict[str, Any]:
    return {field: source[field] for field in HARVESTED_FIELDS if field != "harvest_root"}


def _segment_root_material(segment: Dict[str, Any]) -> Dict[str, Any]:
    return {field: segment[field] for field in SEGMENT_FIELDS if field != "localization_root"}


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    return {field: refusal[field] for field in REFUSAL_FIELDS if field != "refusal_root"}


def _validate_harvested_source(source: Dict[str, Any]) -> None:
    if not isinstance(source, dict) or set(source.keys()) != set(HARVESTED_FIELDS):
        raise TemporalContentLocalizationRefusal(
            "REFUSED_MALFORMED_HARVESTED_SOURCE",
            "Harvested temporal source fields do not match upstream schema.",
        )
    for field_name in HARVESTED_FIELDS:
        if field_name in ("http_status", "content_length", "manual_review_required"):
            continue
        _require_nonempty_string(source, field_name, "REFUSED_MALFORMED_HARVESTED_SOURCE")
    if source["time_direction"] not in TIME_DIRECTIONS:
        raise TemporalContentLocalizationRefusal(
            "REFUSED_MALFORMED_HARVESTED_SOURCE",
            f"Unsupported time_direction: {source['time_direction']}.",
        )
    if source["source_type"] not in SOURCE_TYPES:
        raise TemporalContentLocalizationRefusal(
            "REFUSED_MALFORMED_HARVESTED_SOURCE",
            f"Unsupported source_type: {source['source_type']}.",
        )
    if not _is_public_url(source["url"]):
        raise TemporalContentLocalizationRefusal(
            "REFUSED_MALFORMED_HARVESTED_SOURCE",
            "Harvested temporal source URL must be public HTTP(S).",
        )
    if not isinstance(source["http_status"], int) or not (200 <= source["http_status"] < 400):
        raise TemporalContentLocalizationRefusal(
            "REFUSED_MALFORMED_HARVESTED_SOURCE",
            "Harvested temporal source http_status must be 200-399.",
        )
    if not isinstance(source["content_length"], int) or source["content_length"] <= 0:
        raise TemporalContentLocalizationRefusal(
            "REFUSED_MALFORMED_HARVESTED_SOURCE",
            "Harvested temporal source content_length must be positive.",
        )
    if source["manual_review_required"] is not True:
        raise TemporalContentLocalizationRefusal(
            "REFUSED_MALFORMED_HARVESTED_SOURCE",
            "Harvested temporal source manual_review_required must remain true.",
        )
    if source["metadata_hash"] != _hash_json(_harvested_metadata_material(source)):
        raise TemporalContentLocalizationRefusal(
            "REFUSED_HARVESTED_METADATA_HASH_MISMATCH",
            f"metadata_hash mismatch for {source['source_id']}.",
        )
    if source["harvest_root"] != _hash_json(_harvest_root_material(source)):
        raise TemporalContentLocalizationRefusal(
            "REFUSED_HARVEST_ROOT_MISMATCH",
            f"harvest_root mismatch for {source['source_id']}.",
        )


def _load_harvested_sources(harvested_sources_path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(harvested_sources_path)
    if not isinstance(payload, dict):
        raise ValueError("harvested_temporal_sources payload must be a JSON object.")
    if payload.get("schema_version") != UPSTREAM_SCHEMA_VERSION:
        raise ValueError("harvested_temporal_sources schema_version is unsupported.")
    sources = payload.get("harvested_temporal_sources")
    if not isinstance(sources, list):
        raise ValueError("harvested_temporal_sources must contain a list.")
    seen_ids = set()
    for source in sources:
        _validate_harvested_source(source)
        harvested_id = source["harvested_temporal_source_id"]
        if harvested_id in seen_ids:
            raise TemporalContentLocalizationRefusal(
                "REFUSED_DUPLICATE_HARVESTED_SOURCE_ID",
                f"Duplicate harvested_temporal_source_id: {harvested_id}.",
            )
        seen_ids.add(harvested_id)
    return sources


def _validate_optional_summary(summary_path: Path, harvested_count: int) -> None:
    summary = _load_json(summary_path)
    if not summary:
        return
    if summary.get("temporal_source_harvester_status") not in UPSTREAM_STATUSES:
        raise ValueError("Temporal source harvester summary status is invalid.")
    if summary.get("harvested_temporal_source_count") != harvested_count:
        raise ValueError("Temporal source harvester summary count does not match payload.")
    for counter_name in ("content_invented", "quotes_created", "timestamps_created", "claims_created", "contradictions_created"):
        if summary.get(counter_name) != 0:
            raise TemporalContentLocalizationRefusal(
                "REFUSED_UPSTREAM_GUARDRAIL_FAILURE",
                f"Upstream harvester guardrail {counter_name} is not closed.",
            )
    if not _closed_flags(summary):
        raise TemporalContentLocalizationRefusal(
            "REFUSED_UPSTREAM_GUARDRAIL_FAILURE",
            "Temporal source harvester summary guardrails must remain closed.",
        )


def _schema_payload() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "upstream_schema_version": UPSTREAM_SCHEMA_VERSION,
        "temporal_content_localization_only": True,
        "harvested_source_fields": list(HARVESTED_FIELDS),
        "localized_temporal_segment_fields": list(SEGMENT_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "modes": ["dry-run", "localize"],
        "max_segment_chars": MAX_SEGMENT_CHARS,
        "max_fetch_bytes": 2_000_000,
        "localization_methods": [
            "html_visible_text_chunks_v1",
            "pdf_stream_text_chunks_v1",
        ],
        "guardrails": {
            "approved_evidence": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "embeddings_created": 0,
            "production_ready": False,
            "quotes_created": 0,
            "timestamps_created": 0,
        },
    }


def _normalize_text(value: str) -> str:
    text = html.unescape(value)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_line(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _looks_like_navigation(line: str) -> bool:
    lowered = line.lower().strip()
    if len(lowered) < 20:
        return True
    nav_terms = (
        "menu",
        "skip to content",
        "privacy policy",
        "cookie",
        "subscribe",
        "share this",
        "follow us",
        "read more",
        "search",
        "login",
        "copyright",
    )
    if lowered in nav_terms or any(lowered.startswith(term) for term in nav_terms):
        return True
    words = lowered.split()
    if len(words) <= 4 and not re.search(r"[.!?;:]", lowered):
        return True
    return False


def _extract_html_text(content_bytes: bytes) -> str:
    parser = _VisibleBodyParser()
    parser.feed(content_bytes.decode("utf-8", errors="replace"))
    raw_lines = "\n".join(parser.parts).splitlines()
    lines: List[str] = []
    seen_counts: Dict[str, int] = {}
    for raw_line in raw_lines:
        line = _clean_line(raw_line)
        if not line or _looks_like_navigation(line):
            continue
        key = line.lower()
        seen_counts[key] = seen_counts.get(key, 0) + 1
        if seen_counts[key] > 1:
            continue
        lines.append(line)
    return _normalize_text("\n".join(lines))


def _decode_pdf_literal(value: bytes) -> str:
    output: List[str] = []
    index = 0
    while index < len(value):
        byte = value[index]
        if byte == 92 and index + 1 < len(value):
            index += 1
            escaped = value[index]
            escapes = {
                ord("n"): "\n",
                ord("r"): "\n",
                ord("t"): "\t",
                ord("b"): "\b",
                ord("f"): "\f",
                ord("("): "(",
                ord(")"): ")",
                ord("\\"): "\\",
            }
            if escaped in escapes:
                output.append(escapes[escaped])
            elif 48 <= escaped <= 55:
                octal = bytes([escaped])
                lookahead = 0
                while index + 1 < len(value) and lookahead < 2 and 48 <= value[index + 1] <= 55:
                    index += 1
                    lookahead += 1
                    octal += bytes([value[index]])
                output.append(chr(int(octal, 8)))
            else:
                output.append(chr(escaped))
        else:
            output.append(chr(byte))
        index += 1
    return "".join(output)


def _literal_strings_from_pdf_bytes(payload: bytes) -> List[str]:
    strings: List[str] = []
    index = 0
    while index < len(payload):
        if payload[index:index + 1] != b"(":
            index += 1
            continue
        index += 1
        depth = 1
        escaped = False
        start = index
        while index < len(payload):
            byte = payload[index]
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 40:
                depth += 1
            elif byte == 41:
                depth -= 1
                if depth == 0:
                    literal = payload[start:index]
                    tail = payload[index + 1:index + 40]
                    if re.match(rb"\s*(?:Tj|'|\"|TJ|\])", tail):
                        strings.append(_decode_pdf_literal(literal))
                    break
            index += 1
        index += 1
    return strings


def _hex_strings_from_pdf_bytes(payload: bytes) -> List[str]:
    strings: List[str] = []
    for match in re.finditer(rb"<([0-9A-Fa-f\s]+)>\s*(?:Tj|'|\"|TJ)", payload):
        compact = re.sub(rb"\s+", b"", match.group(1))
        if len(compact) < 2:
            continue
        if len(compact) % 2:
            compact += b"0"
        try:
            decoded = bytes.fromhex(compact.decode("ascii")).decode("utf-16-be", errors="ignore")
            if not decoded.strip():
                decoded = bytes.fromhex(compact.decode("ascii")).decode("latin-1", errors="ignore")
            strings.append(decoded)
        except (ValueError, UnicodeDecodeError):
            continue
    return strings


def _flate_streams(payload: bytes) -> List[bytes]:
    streams: List[bytes] = []
    pattern = re.compile(rb"<<(?P<dict>.*?)>>\s*stream\r?\n(?P<body>.*?)\r?\nendstream", re.DOTALL)
    for match in pattern.finditer(payload):
        dictionary = match.group("dict")
        body = match.group("body")
        if b"FlateDecode" not in dictionary:
            continue
        try:
            streams.append(zlib.decompress(body))
        except zlib.error:
            try:
                streams.append(zlib.decompress(body.strip()))
            except zlib.error:
                continue
    return streams


def _extract_pdf_text(content_bytes: bytes) -> str:
    candidates = [content_bytes]
    candidates.extend(_flate_streams(content_bytes))
    parts: List[str] = []
    for candidate in candidates:
        parts.extend(_literal_strings_from_pdf_bytes(candidate))
        parts.extend(_hex_strings_from_pdf_bytes(candidate))
    cleaned_parts = []
    for part in parts:
        cleaned = _clean_line(part)
        if len(cleaned) >= 3:
            cleaned_parts.append(cleaned)
    text = _normalize_text("\n".join(cleaned_parts))
    if not text:
        raise TemporalContentLocalizationRefusal(
            "REFUSED_NO_LOCALIZABLE_TEXT",
            "PDF contained no extractable text operands.",
        )
    return text


def _extract_text(source: Dict[str, Any], content_bytes: bytes) -> str:
    content_type = source["content_type"].lower()
    if "text/html" in content_type or "application/xhtml" in content_type:
        text = _extract_html_text(content_bytes)
    elif content_type.startswith("text/") or "application/json" in content_type:
        text = _normalize_text(content_bytes.decode("utf-8", errors="replace"))
    elif "application/pdf" in content_type or source["url"].lower().endswith(".pdf"):
        text = _extract_pdf_text(content_bytes)
    else:
        raise TemporalContentLocalizationRefusal(
            "REFUSED_UNSUPPORTED_CONTENT_TYPE",
            f"Unsupported content_type for temporal localization: {source['content_type']}.",
        )
    if not text:
        raise TemporalContentLocalizationRefusal(
            "REFUSED_NO_LOCALIZABLE_TEXT",
            "Harvested source produced no localizable text.",
        )
    return text


def _fetch_bytes(source: Dict[str, Any]) -> bytes:
    request = urllib.request.Request(
        source["url"],
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; DumaBokoContradictionEngine/2.0; "
                "temporal-content-localization)"
            )
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            content = response.read(2_000_000)
            status = int(response.status)
            if status < 200 or status >= 400:
                raise TemporalContentLocalizationRefusal(
                    "REFUSED_REFETCH_FAILED",
                    f"HTTP status {status} is outside 200-399 during localization refetch.",
                )
            return content
    except TemporalContentLocalizationRefusal:
        raise
    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
        http.client.HTTPException,
        OSError,
    ) as exc:
        raise TemporalContentLocalizationRefusal(
            "REFUSED_REFETCH_FAILED",
            f"Unable to refetch harvested source: {exc}",
        ) from exc


def _chunk_text(text: str) -> List[str]:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{1,}", text) if paragraph.strip()]
    chunks: List[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > MAX_SEGMENT_CHARS:
            if current:
                chunks.append(current)
                current = ""
            words = paragraph.split()
            word_chunk = ""
            for word in words:
                candidate = f"{word_chunk} {word}".strip()
                if len(candidate) > MAX_SEGMENT_CHARS and word_chunk:
                    chunks.append(word_chunk)
                    word_chunk = word
                else:
                    word_chunk = candidate
            if word_chunk:
                chunks.append(word_chunk)
            continue
        candidate = f"{current}\n{paragraph}".strip() if current else paragraph
        if len(candidate) > MAX_SEGMENT_CHARS and current:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk.strip()]


def _make_segment(source: Dict[str, Any], segment_index: int, text: str) -> Dict[str, Any]:
    segment = {
        "localized_segment_id": f"TEMPORAL_SEGMENT_{source['harvested_temporal_source_id']}_{segment_index:04d}",
        "harvested_temporal_source_id": source["harvested_temporal_source_id"],
        "source_id": source["source_id"],
        "time_direction": source["time_direction"],
        "source_type": source["source_type"],
        "url": source["url"],
        "segment_index": segment_index,
        "segment_text": text,
        "segment_sha256": _sha256_text(text),
        "publisher": source["publisher"],
        "published_date": source["published_date"],
        "topic": source["topic"],
        "manual_review_required": True,
        "localization_root": "",
    }
    segment["localization_root"] = _hash_json(_segment_root_material(segment))
    return segment


def validate_segment(segment: Dict[str, Any]) -> None:
    if set(segment.keys()) != set(SEGMENT_FIELDS):
        raise ValueError("Localized temporal segment fields changed unexpectedly.")
    for field_name in SEGMENT_FIELDS:
        if field_name in ("segment_index", "manual_review_required"):
            continue
        value = segment.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"LocalizedTemporalSegment.{field_name} must be non-empty.")
    if segment["time_direction"] not in TIME_DIRECTIONS:
        raise ValueError("LocalizedTemporalSegment.time_direction unsupported.")
    if segment["source_type"] not in SOURCE_TYPES:
        raise ValueError("LocalizedTemporalSegment.source_type unsupported.")
    if not isinstance(segment["segment_index"], int) or segment["segment_index"] < 1:
        raise ValueError("LocalizedTemporalSegment.segment_index must be positive.")
    if segment["segment_sha256"] != _sha256_text(segment["segment_text"]):
        raise ValueError(f"segment_sha256 mismatch for {segment['localized_segment_id']}.")
    if segment["manual_review_required"] is not True:
        raise ValueError("LocalizedTemporalSegment.manual_review_required must remain true.")
    if segment["localization_root"] != _hash_json(_segment_root_material(segment)):
        raise ValueError(f"localization_root mismatch for {segment['localized_segment_id']}.")


def _make_refusal(sequence_number: int, source: Dict[str, Any], code: str, reason: str) -> Dict[str, Any]:
    refusal = {
        "refusal_id": f"TEMPORAL_CONTENT_LOCALIZATION_REFUSAL_{sequence_number:06d}",
        "source_id": str(source.get("source_id") or "UNKNOWN_SOURCE_ID"),
        "refusal_code": code,
        "refusal_reason": reason,
        "manual_review_required": True,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Temporal content localization refusal fields changed unexpectedly.")
    for field_name in REFUSAL_FIELDS:
        if field_name == "manual_review_required":
            continue
        value = refusal.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"TemporalContentLocalizationRefusal.{field_name} must be non-empty.")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("TemporalContentLocalizationRefusal.manual_review_required must remain true.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}.")


def _localize_source(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    content = _fetch_bytes(source)
    if not content:
        raise TemporalContentLocalizationRefusal(
            "REFUSED_NO_LOCALIZABLE_TEXT",
            "Refetched harvested source returned no content bytes.",
        )
    if _sha256_bytes(content) != source["content_sha256"]:
        raise TemporalContentLocalizationRefusal(
            "REFUSED_CONTENT_HASH_MISMATCH",
            f"Refetched content SHA-256 does not match harvested source {source['source_id']}.",
        )
    text = _extract_text(source, content)
    chunks = _chunk_text(text)
    if not chunks:
        raise TemporalContentLocalizationRefusal(
            "REFUSED_NO_LOCALIZABLE_TEXT",
            "Text extraction produced no deterministic segments.",
        )
    return [_make_segment(source, offset + 1, chunk) for offset, chunk in enumerate(chunks)]


def _status_for(mode: str, segment_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if segment_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if segment_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _summary_root_material(summary: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {
        "temporal_content_localization_root",
        "temporal_content_localization_schema_hash",
        "temporal_content_localization_report_hash",
    }
    return {key: value for key, value in summary.items() if key not in excluded}


def _build_report(
    status: str,
    mode: str,
    harvested_count: int,
    segments: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    segment_lines = ["- None"]
    if segments:
        segment_lines = []
        for segment in segments[:20]:
            preview = segment["segment_text"][:160].replace("\n", " ")
            segment_lines.extend(
                [
                    f"- {segment['localized_segment_id']}",
                    f"  - Source: {segment['source_id']}",
                    f"  - URL: {segment['url']}",
                    f"  - Preview: {preview}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Source: {refusal['source_id']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Temporal Content Localization v2",
            "",
            "This lane extracts deterministic reviewable text segments from "
            "harvested temporal sources. It does not summarize, infer meaning, "
            "create quotes, timestamps, claims, contradictions, embeddings, "
            "production readiness, or approved evidence.",
            "",
            "## Summary",
            f"- temporal_content_localization_status: {status}",
            f"- mode: {mode}",
            f"- harvested_temporal_source_count: {harvested_count}",
            f"- localized_temporal_segment_count: {len(segments)}",
            f"- refusal_count: {len(refusals)}",
            f"- temporal_content_localization_root: {root}",
            "",
            "## First Localized Segments",
            *segment_lines,
            "",
            "## First Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- Quotes Created: 0",
            "- Timestamps Created: 0",
            "- Claims Created: 0",
            "- Contradictions Created: 0",
            "- Embeddings Created: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "",
        ]
    )


def build_temporal_content_localization(
    mode: str = "dry-run",
    harvested_sources_path: Path = DEFAULT_HARVESTED_SOURCES,
    harvester_summary_path: Path = DEFAULT_HARVESTER_SUMMARY,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "localize"):
        raise ValueError("mode must be 'dry-run' or 'localize'.")

    harvested_sources = _load_harvested_sources(harvested_sources_path)
    _validate_optional_summary(harvester_summary_path, len(harvested_sources))
    schema = _schema_payload()
    schema_hash = _hash_json(schema)

    segments: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    if mode == "localize":
        for source in harvested_sources:
            try:
                localized = _localize_source(source)
                for segment in localized:
                    validate_segment(segment)
                segments.extend(localized)
            except TemporalContentLocalizationRefusal as exc:
                refusal = _make_refusal(len(refusals) + 1, source, exc.code, exc.reason)
                validate_refusal(refusal)
                refusals.append(refusal)

    segment_roots = [segment["localization_root"] for segment in segments]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    status = _status_for(mode, len(segments), len(refusals))
    summary = {
        "temporal_content_localization_status": status,
        "mode": mode,
        "harvested_temporal_source_count": len(harvested_sources),
        "localized_temporal_segment_count": len(segments),
        "refusal_count": len(refusals),
        "before_segment_count": sum(1 for segment in segments if segment["time_direction"] == "BEFORE"),
        "after_segment_count": sum(1 for segment in segments if segment["time_direction"] == "AFTER"),
        "source_type_segment_counts": {
            source_type: sum(1 for segment in segments if segment["source_type"] == source_type)
            for source_type in SOURCE_TYPES
        },
        "source_ids_processed": [source["source_id"] for source in harvested_sources],
        "source_content_sha256s": [source["content_sha256"] for source in harvested_sources],
        "source_harvest_roots": [source["harvest_root"] for source in harvested_sources],
        "localized_segment_roots": segment_roots,
        "refusal_roots": refusal_roots,
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "source_lineage_preserved": True,
        "temporal_content_localization_schema_hash": schema_hash,
        "temporal_content_localization_report_hash": "",
        "temporal_content_localization_root": "",
        "content_summarized": 0,
        "meaning_inferred": 0,
        "quotes_created": 0,
        "timestamps_created": 0,
        "claims_created": 0,
        "contradictions_created": 0,
        "embeddings_created": 0,
        "sentiment_classifications_created": 0,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    summary["temporal_content_localization_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(harvested_sources),
        segments,
        refusals,
        summary["temporal_content_localization_root"],
    )
    summary["temporal_content_localization_report_hash"] = _sha256_text(report)
    summary["temporal_content_localization_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(harvested_sources),
        segments,
        refusals,
        summary["temporal_content_localization_root"],
    )
    if mode == "dry-run" and (segments or refusals):
        raise ValueError("Dry-run must validate harvested temporal sources only.")
    for counter_name in (
        "content_summarized",
        "meaning_inferred",
        "quotes_created",
        "timestamps_created",
        "claims_created",
        "contradictions_created",
        "embeddings_created",
        "sentiment_classifications_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0.")
    if not _closed_flags(summary):
        raise ValueError("Temporal content localization guardrails must remain closed.")

    segments_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "localized_temporal_segments": segments,
    }
    refusals_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "temporal_content_localization_refusals": refusals,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(output_dir / SEGMENTS_OUTPUT.name, segments_payload)
    _write_json(output_dir / REFUSALS_OUTPUT.name, refusals_payload)
    _write_json(output_dir / SCHEMA_OUTPUT.name, schema)
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    return {
        "summary": summary,
        "localized_temporal_segments": segments,
        "temporal_content_localization_refusals": refusals,
        "schema": schema,
        "report": report,
    }


__all__ = ["build_temporal_content_localization"]
