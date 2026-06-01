#!/usr/bin/env python3
"""
Real Evidence Gathering Engine v2.

Gathers refusal-first public evidence references into the image-derived
integrated packet structure. Dry-run mode uses deterministic demo evidence
only. From-seeds mode never invents sources, quotes, timestamps, or transcript
lines; unverifiable inputs become refusal records.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json
import re
import shutil
import subprocess
import tempfile


DEFAULT_SEED_FILE = Path("inputs/real_evidence_seeds/duma_boko_seed_sources.json")

DEFAULT_OUTPUT_DIR = Path("outputs/real_evidence_gathering_engine")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "real_evidence_gathering_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "real_evidence_gathering_summary.json"
PACKETS_OUTPUT = DEFAULT_OUTPUT_DIR / "real_evidence_packets.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "real_evidence_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "real_evidence_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "real_evidence_schema.json"

SCHEMA_VERSION = "real_evidence_gathering_engine_v2"
DEMO_STATUS = "REAL_EVIDENCE_GATHERING_DEMO_CANDIDATE"
CANDIDATE_STATUS = "REAL_EVIDENCE_GATHERING_CANDIDATE"
PARTIAL_STATUS = "REAL_EVIDENCE_GATHERING_PARTIAL"
REFUSED_STATUS = "REAL_EVIDENCE_GATHERING_REFUSED"

VERIFIED = "VERIFIED"
PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
REFUSED_MISSING_SOURCE_URL = "REFUSED_MISSING_SOURCE_URL"
REFUSED_MISSING_TRANSCRIPT = "REFUSED_MISSING_TRANSCRIPT"
REFUSED_MISSING_TIMESTAMP = "REFUSED_MISSING_TIMESTAMP"
REFUSED_MISSING_QUOTE = "REFUSED_MISSING_QUOTE"
REFUSED_UNSUPPORTED_SOURCE_TYPE = "REFUSED_UNSUPPORTED_SOURCE_TYPE"
MISSING_TRANSCRIPT_TOOL = "REAL_EVIDENCE_BLOCKED_MISSING_TRANSCRIPT_TOOL"

PACKET_STATUS = "candidate_real_evidence_packet"
DEMO_PACKET_STATUS = "candidate_demo_real_evidence_packet"
REFUSAL_STATUS = "candidate_real_evidence_refusal"

SUPPORTED_SOURCE_TYPES = ("video", "document", "transcript", "web")

REQUIRED_SEED_FIELDS = (
    "seed_id",
    "case_id",
    "source_type",
    "source_url",
    "source_title",
    "speaker_name",
    "speaker_party",
    "expected_topic",
    "expected_claim_keywords",
    "manual_timestamp_hint",
    "notes",
)

OPTIONAL_SEED_FIELDS = (
    "manual_quote_text",
    "manual_video_timestamp_start",
    "manual_video_timestamp_end",
    "manual_transcript_start_line",
    "manual_transcript_end_line",
    "local_transcript_path",
    "screenshot_reference",
    "document_reference",
    "document_page_start",
    "document_page_end",
)

INTEGRATED_OUTPUT_SECTIONS = (
    "source_details",
    "source_ownership",
    "speaker_political_leader",
    "original_promise",
    "current_government_position",
    "evidence_collection",
    "final_report_validation_checklist",
)

EVIDENCE_ITEM_FIELDS = (
    "evidence_id",
    "evidence_type",
    "source_reference",
    "video_url",
    "video_title",
    "video_timestamp_start",
    "video_timestamp_end",
    "audio_timestamp_start",
    "audio_timestamp_end",
    "transcript_start_line",
    "transcript_end_line",
    "quote_text",
    "screenshot_reference",
    "document_reference",
    "document_page_start",
    "document_page_end",
    "hash_sha256",
    "verification_status",
    "localization_status",
    "refusal_reason",
)

PACKET_FIELDS = (
    "packet_id",
    "case_id",
    "source_details",
    "source_ownership",
    "speaker_political_leader",
    "original_promise",
    "current_government_position",
    "evidence_collection",
    "final_report_validation_checklist",
    "packet_root",
    "packet_status",
)

REFUSAL_FIELDS = (
    "refusal_id",
    "seed_id",
    "case_id",
    "source_type",
    "source_url",
    "refusal_status",
    "refusal_reason",
    "missing_fields",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "refusal_root",
)

REPORT_DISCLAIMER = (
    "This report documents evidence gathered and localized. It does not by "
    "itself prove contradiction until claim extraction, normalization, graph "
    "analysis, proof chain, and case assembly run successfully."
)


@dataclass
class EvidenceSeed:
    seed_id: str
    case_id: str
    source_type: str
    source_url: str
    source_title: str
    speaker_name: str
    speaker_party: str
    expected_topic: str
    expected_claim_keywords: List[str]
    manual_timestamp_hint: str
    notes: str
    manual_quote_text: str = ""
    manual_video_timestamp_start: str = ""
    manual_video_timestamp_end: str = ""
    manual_transcript_start_line: int = 0
    manual_transcript_end_line: int = 0
    local_transcript_path: str = ""
    screenshot_reference: str = ""
    document_reference: str = ""
    document_page_start: int = 0
    document_page_end: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RefusalRecord:
    refusal_id: str
    seed_id: str
    case_id: str
    source_type: str
    source_url: str
    refusal_status: str
    refusal_reason: str
    missing_fields: List[str]
    production_ready: bool
    approved_evidence: int
    public_ready: bool
    institutional_ready: bool
    refusal_root: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _has_video_anchor(item: Dict[str, Any]) -> bool:
    return bool(item.get("video_timestamp_start")) and bool(item.get("video_timestamp_end"))


def _has_audio_anchor(item: Dict[str, Any]) -> bool:
    return bool(item.get("audio_timestamp_start")) and bool(item.get("audio_timestamp_end"))


def _has_transcript_anchor(item: Dict[str, Any]) -> bool:
    start = _safe_int(item.get("transcript_start_line"))
    end = _safe_int(item.get("transcript_end_line"))
    return start > 0 and end >= start


def _has_screenshot_anchor(item: Dict[str, Any]) -> bool:
    return bool(item.get("screenshot_reference"))


def _has_document_anchor(item: Dict[str, Any]) -> bool:
    start = _safe_int(item.get("document_page_start"))
    end = _safe_int(item.get("document_page_end"))
    return start > 0 and end >= start


def _has_any_anchor(item: Dict[str, Any]) -> bool:
    return any(
        (
            _has_video_anchor(item),
            _has_audio_anchor(item),
            _has_transcript_anchor(item),
            _has_screenshot_anchor(item),
            _has_document_anchor(item),
        )
    )


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _parse_timestamp_hint(value: str) -> Tuple[str, str]:
    if not value:
        return "", ""
    matches = re.findall(r"\d{1,2}:\d{2}(?::\d{2})?", value)
    if len(matches) >= 2:
        return _normalize_timestamp(matches[0]), _normalize_timestamp(matches[1])
    return "", ""


def _normalize_timestamp(value: str) -> str:
    if not value:
        return ""
    parts = value.strip().split(":")
    if len(parts) == 2:
        return f"00:{int(parts[0]):02d}:{int(parts[1]):02d}"
    if len(parts) == 3:
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}:{int(parts[2]):02d}"
    return value.strip()


def _seed_from_dict(data: Dict[str, Any]) -> EvidenceSeed:
    for field_name in REQUIRED_SEED_FIELDS:
        if field_name not in data:
            raise ValueError(f"Seed missing required field: {field_name}")
    keywords = data.get("expected_claim_keywords")
    if not isinstance(keywords, list):
        raise ValueError("Seed.expected_claim_keywords must be a list")
    return EvidenceSeed(
        seed_id=str(data.get("seed_id", "")),
        case_id=str(data.get("case_id", "")),
        source_type=str(data.get("source_type", "")),
        source_url=str(data.get("source_url", "")),
        source_title=str(data.get("source_title", "")),
        speaker_name=str(data.get("speaker_name", "")),
        speaker_party=str(data.get("speaker_party", "")),
        expected_topic=str(data.get("expected_topic", "")),
        expected_claim_keywords=[str(keyword) for keyword in keywords],
        manual_timestamp_hint=str(data.get("manual_timestamp_hint", "")),
        notes=str(data.get("notes", "")),
        manual_quote_text=str(data.get("manual_quote_text", "")),
        manual_video_timestamp_start=str(data.get("manual_video_timestamp_start", "")),
        manual_video_timestamp_end=str(data.get("manual_video_timestamp_end", "")),
        manual_transcript_start_line=_safe_int(data.get("manual_transcript_start_line")),
        manual_transcript_end_line=_safe_int(data.get("manual_transcript_end_line")),
        local_transcript_path=str(data.get("local_transcript_path", "")),
        screenshot_reference=str(data.get("screenshot_reference", "")),
        document_reference=str(data.get("document_reference", "")),
        document_page_start=_safe_int(data.get("document_page_start")),
        document_page_end=_safe_int(data.get("document_page_end")),
    )


def _demo_seeds() -> List[EvidenceSeed]:
    return [
        EvidenceSeed(
            seed_id="DEMO_SEED_001",
            case_id="DEMO_REAL_CASE_001",
            source_type="video",
            source_url="demo://duma-boko/employment-promise",
            source_title="Demo Duma Boko employment promise video",
            speaker_name="Duma Boko",
            speaker_party="demo_party",
            expected_topic="employment_promise",
            expected_claim_keywords=["employment", "jobs"],
            manual_timestamp_hint="00:12:31-00:12:48",
            notes="Dry-run demo seed. This is not real evidence.",
            manual_quote_text="Demo localized quote for an employment promise evidence packet.",
            manual_video_timestamp_start="00:12:31",
            manual_video_timestamp_end="00:12:48",
            manual_transcript_start_line=145,
            manual_transcript_end_line=151,
        ),
        EvidenceSeed(
            seed_id="DEMO_SEED_002",
            case_id="DEMO_REAL_CASE_002",
            source_type="video",
            source_url="demo://duma-boko/current-position",
            source_title="Demo Duma Boko current government position video",
            speaker_name="Duma Boko",
            speaker_party="demo_party",
            expected_topic="current_government_position",
            expected_claim_keywords=["programme", "status"],
            manual_timestamp_hint="00:04:10-00:04:28",
            notes="Dry-run demo seed. This is not real evidence.",
            manual_quote_text=(
                "Demo localized quote for a current government position evidence packet."
            ),
            manual_video_timestamp_start="00:04:10",
            manual_video_timestamp_end="00:04:28",
            manual_transcript_start_line=55,
            manual_transcript_end_line=61,
        ),
        EvidenceSeed(
            seed_id="DEMO_SEED_003",
            case_id="DEMO_REAL_CASE_003",
            source_type="document",
            source_url="demo://duma-boko/implementation-status",
            source_title="Demo Duma Boko implementation status document",
            speaker_name="Duma Boko",
            speaker_party="demo_party",
            expected_topic="implementation_status",
            expected_claim_keywords=["implementation", "status"],
            manual_timestamp_hint="",
            notes="Dry-run demo seed. This is not real evidence.",
            manual_quote_text=(
                "Demo localized quote for an implementation status evidence packet."
            ),
            screenshot_reference="screenshots/demo_real_case_003_implementation_status.png",
            document_reference="demo://duma-boko/implementation-status",
            document_page_start=3,
            document_page_end=4,
        ),
    ]


def _load_seed_file(path: Path) -> List[EvidenceSeed]:
    payload = _load_json(path)
    seed_sources = payload.get("seed_sources")
    if not isinstance(seed_sources, list):
        raise ValueError("Seed file must contain a seed_sources list")
    return [_seed_from_dict(seed) for seed in seed_sources]


def _ytdlp_path() -> str:
    return shutil.which("yt-dlp") or ""


def _yt_dlp_metadata(source_url: str) -> Dict[str, Any]:
    executable = _ytdlp_path()
    if not executable:
        return {}
    command = [
        executable,
        "--dump-single-json",
        "--skip-download",
        "--no-warnings",
        source_url,
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return {}
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {}


def _parse_vtt(path: Path) -> List[str]:
    lines: List[str] = []
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line == "WEBVTT" or line.startswith(("Kind:", "Language:", "NOTE")):
            continue
        if "-->" in line or line.isdigit():
            continue
        clean = re.sub(r"<[^>]+>", "", line)
        clean = _normalize_whitespace(clean)
        if clean:
            lines.append(clean)
    return lines


def _yt_dlp_transcript_lines(source_url: str) -> List[str]:
    executable = _ytdlp_path()
    if not executable:
        return []
    with tempfile.TemporaryDirectory() as temp_dir:
        output_template = str(Path(temp_dir) / "%(id)s.%(ext)s")
        command = [
            executable,
            "--skip-download",
            "--write-auto-subs",
            "--write-subs",
            "--sub-langs",
            "en.*",
            "--sub-format",
            "vtt",
            "--output",
            output_template,
            source_url,
        ]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if completed.returncode != 0:
            return []
        transcript_lines: List[str] = []
        for vtt_path in sorted(Path(temp_dir).glob("*.vtt")):
            transcript_lines.extend(_parse_vtt(vtt_path))
        return transcript_lines


def _local_transcript_lines(seed: EvidenceSeed) -> List[str]:
    if not seed.local_transcript_path:
        return []
    path = Path(seed.local_transcript_path)
    if not path.exists() or not path.is_file():
        return []
    if path.suffix.lower() == ".vtt":
        return _parse_vtt(path)
    return [
        _normalize_whitespace(line)
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if _normalize_whitespace(line)
    ]


def _quote_from_lines(
    lines: List[str],
    keywords: List[str],
    start_line: int,
    end_line: int,
) -> Tuple[str, int, int]:
    if start_line > 0 and end_line >= start_line and end_line <= len(lines):
        quote = _normalize_whitespace(" ".join(lines[start_line - 1 : end_line]))
        return quote, start_line, end_line
    lowered_keywords = [keyword.lower() for keyword in keywords if keyword.strip()]
    if lowered_keywords:
        for index, line in enumerate(lines, start=1):
            lowered_line = line.lower()
            if all(keyword in lowered_line for keyword in lowered_keywords):
                return line, index, index
        for index, line in enumerate(lines, start=1):
            lowered_line = line.lower()
            if any(keyword in lowered_line for keyword in lowered_keywords):
                return line, index, index
    return "", 0, 0


def _source_reference(seed: EvidenceSeed) -> str:
    return f"{seed.seed_id}:{seed.source_url}"


def _evidence_hash_material(item: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(item)
    material.pop("hash_sha256", None)
    return material


def _assign_evidence_hash(item: Dict[str, Any]) -> Dict[str, Any]:
    item["hash_sha256"] = _hash_json(_evidence_hash_material(item))
    return item


def _packet_hash_material(packet: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(packet)
    material.pop("packet_root", None)
    return material


def _assign_packet_root(packet: Dict[str, Any]) -> Dict[str, Any]:
    packet["packet_root"] = _hash_json(_packet_hash_material(packet))
    return packet


def _refusal_hash_material(refusal: RefusalRecord) -> Dict[str, Any]:
    material = refusal.to_dict()
    material.pop("refusal_root", None)
    return material


def _assign_refusal_root(refusal: RefusalRecord) -> RefusalRecord:
    refusal.refusal_root = _hash_json(_refusal_hash_material(refusal))
    return refusal


def _make_refusal(
    seed: EvidenceSeed,
    reason: str,
    missing_fields: List[str],
) -> RefusalRecord:
    refusal = RefusalRecord(
        refusal_id=f"REFUSAL_{seed.seed_id}",
        seed_id=seed.seed_id,
        case_id=seed.case_id,
        source_type=seed.source_type,
        source_url=seed.source_url,
        refusal_status=REFUSAL_STATUS,
        refusal_reason=reason,
        missing_fields=missing_fields,
        production_ready=False,
        approved_evidence=0,
        public_ready=False,
        institutional_ready=False,
        refusal_root="",
    )
    return _assign_refusal_root(refusal)


def _base_evidence_item(seed: EvidenceSeed, metadata: Dict[str, Any]) -> Dict[str, Any]:
    title = seed.source_title or str(metadata.get("title") or "")
    timestamp_start, timestamp_end = _parse_timestamp_hint(seed.manual_timestamp_hint)
    video_start = seed.manual_video_timestamp_start or timestamp_start
    video_end = seed.manual_video_timestamp_end or timestamp_end
    source_reference = _source_reference(seed)
    return {
        "evidence_id": f"EVIDENCE_{seed.seed_id}",
        "evidence_type": seed.source_type,
        "source_reference": source_reference,
        "video_url": seed.source_url if seed.source_type == "video" else "",
        "video_title": title if seed.source_type == "video" else "",
        "video_timestamp_start": video_start,
        "video_timestamp_end": video_end,
        "audio_timestamp_start": video_start if seed.source_type == "video" else "",
        "audio_timestamp_end": video_end if seed.source_type == "video" else "",
        "transcript_start_line": seed.manual_transcript_start_line,
        "transcript_end_line": seed.manual_transcript_end_line,
        "quote_text": _normalize_whitespace(seed.manual_quote_text),
        "screenshot_reference": seed.screenshot_reference,
        "document_reference": seed.document_reference
        or (seed.source_url if seed.source_type == "document" else ""),
        "document_page_start": seed.document_page_start,
        "document_page_end": seed.document_page_end,
        "hash_sha256": "",
        "verification_status": "",
        "localization_status": "",
        "refusal_reason": "",
    }


def _packet_from_seed(
    seed: EvidenceSeed,
    item: Dict[str, Any],
    metadata: Dict[str, Any],
    demo_mode: bool,
) -> Dict[str, Any]:
    title = seed.source_title or str(metadata.get("title") or "")
    owner_name = str(metadata.get("uploader") or metadata.get("channel") or "unknown")
    original_promise_text = item["quote_text"] if "promise" in seed.expected_topic else ""
    current_position_text = item["quote_text"] if "promise" not in seed.expected_topic else ""
    packet = {
        "packet_id": f"REAL_PACKET_{seed.seed_id}",
        "case_id": seed.case_id,
        "source_details": {
            "source_type": seed.source_type,
            "source_title": title,
            "source_url": seed.source_url,
            "source_platform": str(metadata.get("extractor_key") or ""),
            "source_reference_id": seed.seed_id,
            "expected_topic": seed.expected_topic,
            "expected_claim_keywords": seed.expected_claim_keywords,
            "demo_mode": demo_mode,
        },
        "source_ownership": {
            "ownership_type": "public_source_reference",
            "owner_name": owner_name,
            "verification_status": item["verification_status"],
            "ownership_notes": seed.notes,
        },
        "speaker_political_leader": {
            "speaker_name": seed.speaker_name,
            "political_party": seed.speaker_party,
            "speaker_role": "political_leader",
            "authority_context": "real_evidence_seed",
        },
        "original_promise": {
            "promise_text": original_promise_text,
            "promise_summary": original_promise_text,
            "promise_category": seed.expected_topic,
            "promise_source_reference": item["source_reference"],
        },
        "current_government_position": {
            "position_text": current_position_text,
            "position_summary": current_position_text,
            "position_category": seed.expected_topic,
            "position_source_reference": item["source_reference"],
        },
        "evidence_collection": {
            "evidence_items": [item],
            "evidence_count": 1,
            "collection_status": item["verification_status"],
        },
        "final_report_validation_checklist": {
            "source_details_present": True,
            "source_ownership_present": True,
            "speaker_political_leader_present": True,
            "original_promise_present": True,
            "current_government_position_present": True,
            "evidence_collection_present": True,
            "source_url_present": bool(seed.source_url.strip()),
            "quote_present": bool(item["quote_text"].strip()),
            "localization_anchor_present": _has_any_anchor(item),
            "hash_present": _is_nonzero_hash(item["hash_sha256"]),
            "deterministic_json": True,
            "sha256_roots": True,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
            "no_generated_outputs_committed": True,
        },
        "packet_root": "",
        "packet_status": DEMO_PACKET_STATUS if demo_mode else PACKET_STATUS,
    }
    return _assign_packet_root(packet)


def _process_demo_seed(seed: EvidenceSeed) -> Tuple[Optional[Dict[str, Any]], Optional[RefusalRecord]]:
    item = _base_evidence_item(seed, {})
    item["verification_status"] = VERIFIED
    item["localization_status"] = "demo_localized"
    item = _assign_evidence_hash(item)
    packet = _packet_from_seed(seed, item, {}, demo_mode=True)
    return packet, None


def _process_real_seed(seed: EvidenceSeed) -> Tuple[Optional[Dict[str, Any]], Optional[RefusalRecord]]:
    if not seed.source_url.strip():
        return None, _make_refusal(seed, REFUSED_MISSING_SOURCE_URL, ["source_url"])
    if seed.source_type not in SUPPORTED_SOURCE_TYPES:
        return None, _make_refusal(seed, REFUSED_UNSUPPORTED_SOURCE_TYPE, ["source_type"])

    metadata: Dict[str, Any] = {}
    transcript_lines = _local_transcript_lines(seed)
    used_supported_tool = False
    if seed.source_type == "video" and (not transcript_lines and not seed.manual_quote_text.strip()):
        if not _ytdlp_path():
            return None, _make_refusal(seed, MISSING_TRANSCRIPT_TOOL, ["yt-dlp"])
        used_supported_tool = True
        metadata = _yt_dlp_metadata(seed.source_url)
        transcript_lines = _yt_dlp_transcript_lines(seed.source_url)
    elif seed.source_type == "video" and _ytdlp_path():
        metadata = _yt_dlp_metadata(seed.source_url)

    item = _base_evidence_item(seed, metadata)
    if transcript_lines:
        quote, start_line, end_line = _quote_from_lines(
            transcript_lines,
            seed.expected_claim_keywords,
            seed.manual_transcript_start_line,
            seed.manual_transcript_end_line,
        )
        if quote and not item["quote_text"]:
            item["quote_text"] = quote
        if start_line and end_line:
            item["transcript_start_line"] = start_line
            item["transcript_end_line"] = end_line

    if not item["quote_text"].strip():
        return None, _make_refusal(seed, REFUSED_MISSING_QUOTE, ["quote_text"])
    if seed.source_type == "video" and not transcript_lines and not seed.manual_quote_text.strip():
        reason = MISSING_TRANSCRIPT_TOOL if not used_supported_tool else REFUSED_MISSING_TRANSCRIPT
        return None, _make_refusal(seed, reason, ["transcript"])
    if not _has_any_anchor(item):
        return None, _make_refusal(seed, REFUSED_MISSING_TIMESTAMP, ["localization_anchor"])

    if transcript_lines and _has_transcript_anchor(item):
        item["verification_status"] = VERIFIED
        item["localization_status"] = "localized_verified"
    else:
        item["verification_status"] = PARTIALLY_VERIFIED
        item["localization_status"] = "localized_partial"
    item = _assign_evidence_hash(item)
    packet = _packet_from_seed(seed, item, metadata, demo_mode=False)
    return packet, None


def _real_evidence_schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "seed_file": str(DEFAULT_SEED_FILE),
        "required_seed_fields": list(REQUIRED_SEED_FIELDS),
        "optional_seed_fields": list(OPTIONAL_SEED_FIELDS),
        "supported_source_types": list(SUPPORTED_SOURCE_TYPES),
        "top_level_sections": list(INTEGRATED_OUTPUT_SECTIONS),
        "packet_fields": list(PACKET_FIELDS),
        "evidence_item_fields": list(EVIDENCE_ITEM_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "evidence_statuses": [
            VERIFIED,
            PARTIALLY_VERIFIED,
            REFUSED_MISSING_SOURCE_URL,
            REFUSED_MISSING_TRANSCRIPT,
            REFUSED_MISSING_TIMESTAMP,
            REFUSED_MISSING_QUOTE,
            REFUSED_UNSUPPORTED_SOURCE_TYPE,
        ],
        "refusal_reasons": [MISSING_TRANSCRIPT_TOOL],
        "root_rules": {
            "hash_sha256": "sha256 over evidence item excluding hash_sha256",
            "packet_root": "sha256 over evidence packet excluding packet_root",
            "refusal_root": "sha256 over refusal record excluding refusal_root",
            "real_evidence_gathering_engine_root": (
                "sha256 over sorted packet roots and sorted refusal roots"
            ),
        },
        "verified_evidence_rule": (
            "VERIFIED evidence requires source URL, quote text, at least one "
            "localization anchor, and a non-empty SHA-256 hash."
        ),
        "closed_governance_flags": {
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        },
    }


def validate_schema(schema: Dict[str, Any]) -> None:
    if schema.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("real_evidence_schema schema_version changed unexpectedly")
    if schema.get("top_level_sections") != list(INTEGRATED_OUTPUT_SECTIONS):
        raise ValueError("real_evidence_schema top_level_sections changed unexpectedly")
    if schema.get("evidence_item_fields") != list(EVIDENCE_ITEM_FIELDS):
        raise ValueError("real_evidence_schema evidence_item_fields changed unexpectedly")


def validate_evidence_item(item: Dict[str, Any], packet_source_url: str) -> None:
    if tuple(item.keys()) != EVIDENCE_ITEM_FIELDS:
        raise ValueError("Real evidence item fields changed unexpectedly")
    for field_name in ("evidence_id", "evidence_type", "source_reference", "verification_status"):
        _require_nonempty_string(item, field_name, "RealEvidenceItem")
    if item["verification_status"] == VERIFIED:
        if not packet_source_url.strip():
            raise ValueError("VERIFIED evidence requires a source URL")
        for field_name in ("quote_text", "hash_sha256"):
            _require_nonempty_string(item, field_name, "RealEvidenceItem")
        if not _has_any_anchor(item):
            raise ValueError("VERIFIED evidence requires at least one anchor")
    if item["verification_status"] == PARTIALLY_VERIFIED:
        _require_nonempty_string(item, "quote_text", "RealEvidenceItem")
        _require_nonempty_string(item, "hash_sha256", "RealEvidenceItem")
        if not _has_any_anchor(item):
            raise ValueError("PARTIALLY_VERIFIED evidence requires at least one anchor")
    if not _is_nonzero_hash(item.get("hash_sha256")):
        raise ValueError("RealEvidenceItem.hash_sha256 must be non-zero")
    if item["hash_sha256"] != _hash_json(_evidence_hash_material(item)):
        raise ValueError(f"hash_sha256 mismatch for {item['evidence_id']}")


def validate_packet(packet: Dict[str, Any]) -> None:
    if tuple(packet.keys()) != PACKET_FIELDS:
        raise ValueError("Real evidence packet fields changed unexpectedly")
    for field_name in ("packet_id", "case_id", "packet_root", "packet_status"):
        _require_nonempty_string(packet, field_name, "RealEvidencePacket")
    for section in INTEGRATED_OUTPUT_SECTIONS:
        if section not in packet or not isinstance(packet[section], dict):
            raise ValueError(f"RealEvidencePacket.{section} must be present")
    source_url = str(packet["source_details"].get("source_url") or "")
    items = packet["evidence_collection"].get("evidence_items")
    if not isinstance(items, list) or not items:
        raise ValueError("Real evidence packet must contain evidence items")
    for item in items:
        validate_evidence_item(item, source_url)
    checklist = packet["final_report_validation_checklist"]
    if not _closed_flags(checklist):
        raise ValueError("Final report validation checklist flags must remain closed")
    if packet["packet_root"] != _hash_json(_packet_hash_material(packet)):
        raise ValueError(f"packet_root mismatch for {packet['packet_id']}")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if tuple(refusal.keys()) != REFUSAL_FIELDS:
        raise ValueError("Real evidence refusal fields changed unexpectedly")
    for field_name in ("refusal_id", "seed_id", "case_id", "refusal_status", "refusal_reason"):
        _require_nonempty_string(refusal, field_name, "RealEvidenceRefusal")
    if not _closed_flags(refusal):
        raise ValueError("Real evidence refusal flags must remain closed")
    if not _is_nonzero_hash(refusal.get("refusal_root")):
        raise ValueError("RealEvidenceRefusal.refusal_root must be non-zero")
    material = dict(refusal)
    material.pop("refusal_root", None)
    if refusal["refusal_root"] != _hash_json(material):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}")


def _status_for_mode(mode: str, packets: List[Dict[str, Any]], refusals: List[Dict[str, Any]]) -> str:
    if mode == "dry-run":
        return DEMO_STATUS
    if packets and not refusals:
        return CANDIDATE_STATUS
    if packets and refusals:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _report_section(title: str, rows: List[str]) -> List[str]:
    return [f"## {title}", *rows, ""]


def _build_report(
    mode: str,
    status: str,
    packets: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    engine_root: str,
) -> str:
    verified_rows: List[str] = []
    partial_rows: List[str] = []
    refused_rows: List[str] = []
    for packet in packets:
        item = packet["evidence_collection"]["evidence_items"][0]
        rows = verified_rows if item["verification_status"] == VERIFIED else partial_rows
        rows.extend(
            [
                f"- Case ID: {packet['case_id']}",
                f"  - Packet ID: {packet['packet_id']}",
                f"  - Source URL: {packet['source_details']['source_url']}",
                f"  - Quote Text: {item['quote_text']}",
                f"  - Video Timestamp: {item['video_timestamp_start']} to {item['video_timestamp_end']}",
                f"  - Transcript Lines: {item['transcript_start_line']} to {item['transcript_end_line']}",
                f"  - Screenshot Reference: {item['screenshot_reference']}",
                f"  - Document Page Range: {item['document_page_start']} to {item['document_page_end']}",
                f"  - Evidence Hash: {item['hash_sha256']}",
            ]
        )
    for refusal in refusals:
        refused_rows.extend(
            [
                f"- Case ID: {refusal['case_id']}",
                f"  - Seed ID: {refusal['seed_id']}",
                f"  - Refusal Reason: {refusal['refusal_reason']}",
                f"  - Missing Fields: {', '.join(refusal['missing_fields'])}",
            ]
        )

    if not verified_rows:
        verified_rows = ["- None"]
    if not partial_rows:
        partial_rows = ["- None"]
    if not refused_rows:
        refused_rows = ["- None"]

    lines = [
        "# Real Evidence Gathering Engine v2",
        "",
        REPORT_DISCLAIMER,
        "",
        "## Summary",
        f"- Mode: {mode}",
        f"- real_evidence_status: {status}",
        f"- real_evidence_packet_count: {len(packets)}",
        f"- refusal_count: {len(refusals)}",
        f"- real_evidence_gathering_engine_root: {engine_root}",
        "- production_ready: False",
        "- approved_evidence: 0",
        "",
    ]
    lines.extend(_report_section("Verified Evidence", verified_rows))
    lines.extend(_report_section("Partially Verified Evidence", partial_rows))
    lines.extend(_report_section("Refused Evidence", refused_rows))
    return "\n".join(lines)


def build_real_evidence_gathering_engine(
    mode: str = "dry-run",
    seed_file: Path = DEFAULT_SEED_FILE,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "from-seeds"):
        raise ValueError("mode must be dry-run or from-seeds")

    seeds = _demo_seeds() if mode == "dry-run" else _load_seed_file(seed_file)
    packets: List[Dict[str, Any]] = []
    refusal_records: List[RefusalRecord] = []
    for seed in seeds:
        packet, refusal = (
            _process_demo_seed(seed) if mode == "dry-run" else _process_real_seed(seed)
        )
        if packet is not None:
            packets.append(packet)
        if refusal is not None:
            refusal_records.append(refusal)

    schema = _real_evidence_schema()
    validate_schema(schema)
    refusal_dicts = [refusal.to_dict() for refusal in refusal_records]
    valid_packet_count = 0
    for packet in packets:
        validate_packet(packet)
        valid_packet_count += 1
    for refusal in refusal_dicts:
        validate_refusal(refusal)

    verified_packet_count = sum(
        1
        for packet in packets
        if packet["evidence_collection"]["evidence_items"][0]["verification_status"] == VERIFIED
    )
    partial_packet_count = sum(
        1
        for packet in packets
        if packet["evidence_collection"]["evidence_items"][0]["verification_status"]
        == PARTIALLY_VERIFIED
    )
    packet_roots = [packet["packet_root"] for packet in packets]
    refusal_roots = [refusal["refusal_root"] for refusal in refusal_dicts]
    engine_root = _hash_json(
        {"packet_roots": sorted(packet_roots), "refusal_roots": sorted(refusal_roots)}
    )
    schema_hash = _hash_json(schema)
    status = _status_for_mode(mode, packets, refusal_dicts)
    report = _build_report(mode, status, packets, refusal_dicts, engine_root)
    report_hash = _sha256_text(report)

    summary = {
        "real_evidence_status": status,
        "mode": mode,
        "seed_count": len(seeds),
        "real_evidence_packet_count": len(packets),
        "valid_packet_count": valid_packet_count,
        "verified_packet_count": verified_packet_count,
        "partial_packet_count": partial_packet_count,
        "refusal_count": len(refusal_dicts),
        "real_evidence_schema_ready": True,
        "real_evidence_report_ready": True,
        "real_evidence_schema_hash": schema_hash,
        "real_evidence_report_hash": report_hash,
        "packet_roots": packet_roots,
        "refusal_roots": refusal_roots,
        "real_evidence_gathering_engine_root": engine_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
        "quotes_invented": False,
    }
    payload = {
        "records": [
            {
                "real_evidence_status": status,
                "mode": mode,
                "seed_count": len(seeds),
                "real_evidence_packet_count": len(packets),
                "verified_packet_count": verified_packet_count,
                "refusal_count": len(refusal_dicts),
                "real_evidence_gathering_engine_root": engine_root,
                "production_ready": False,
                "approved_evidence": 0,
                "public_ready": False,
                "institutional_ready": False,
            }
        ]
    }

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(PACKETS_OUTPUT, {"real_evidence_packets": packets})
    _write_json(REFUSALS_OUTPUT, {"real_evidence_refusals": refusal_dicts})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report + "\n")

    return {
        "payload": payload,
        "summary": summary,
        "packets": packets,
        "refusals": refusal_dicts,
        "schema": schema,
        "report": report,
    }
