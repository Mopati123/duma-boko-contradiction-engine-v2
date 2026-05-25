#!/usr/bin/env python3
"""
Auto-collect candidate transcript/caption data for real evidence templates.

This helper produces candidate evidence only. Automated collection never verifies
or approves evidence, never marks release readiness, and never downloads media.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


TEMPLATE_DIR = Path("data/real_evidence_inputs")
TEMPLATE_GLOB = "*.template.json"
OUTPUT_DIR = Path("outputs/real_evidence_auto_collection")
STATUS_OUTPUT = OUTPUT_DIR / "auto_collection_status.json"
SUMMARY_OUTPUT = OUTPUT_DIR / "auto_collection_summary.json"

DISPLAY_FIELDS = ("evidence_id", "case_id", "source_url")
HUMAN_FIELDS = (
    "transcript_text",
    "timestamp_start",
    "timestamp_end",
    "quote_text",
    "speaker",
    "context_summary",
    "case_relevance_note",
    "reviewer",
    "reviewer_notes",
)
ALL_FIELDS = (*DISPLAY_FIELDS, *HUMAN_FIELDS, "verification_status")

AUTO_REVIEWER_NOTES = (
    "Auto-collected candidate only. Human verification required before approval."
)
AUTO_CONTEXT_SUMMARY = (
    "Auto-collected transcript candidate. Human context review required."
)
AUTO_SPEAKER = "Unverified speaker"

CASE_RELEVANCE_NOTES = {
    "CASE_002": (
        "Auto-collected jobs-creation evidence candidate. Human case relevance "
        "review required before approval."
    ),
    "CASE_006": (
        "Auto-collected healthcare evidence candidate. Human case relevance "
        "review required before approval."
    ),
}

STATUSES = {
    "candidate_collected",
    "yt_dlp_missing",
    "captions_unavailable",
    "network_disabled",
    "collection_failed",
}

TIMESTAMP_LINE_RE = re.compile(
    r"^(?P<start>\d{1,2}:\d{2}(?::\d{2})?(?:[\.,]\d{1,3})?)\s+-->\s+"
    r"(?P<end>\d{1,2}:\d{2}(?::\d{2})?(?:[\.,]\d{1,3})?)"
)
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class CaptionSegment:
    timestamp_start: str
    timestamp_end: str
    text: str


@dataclass
class AutoCollectionRecord:
    evidence_id: str
    case_id: str
    source_url: str
    collection_status: str
    message: str
    candidate_available: bool
    would_write_template: bool
    backup_path: str
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    candidate_fields: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect candidate captions for real evidence input templates."
    )
    parser.add_argument(
        "--evidence-id",
        help="Collect for only one evidence item, for example VID_JOBS_001.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not modify templates or create backups. This is the default.",
    )
    parser.add_argument(
        "--write-candidates",
        action="store_true",
        help="Write candidate fields to templates and create .bak backups.",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Do not invoke yt-dlp; record that manual entry is required.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        help="Timeout for each yt-dlp subprocess call.",
    )
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def normalize_record(data: Dict[str, object]) -> Dict[str, str]:
    return {field: stringify(data.get(field, "")) for field in ALL_FIELDS}


def load_templates(evidence_id: str = "") -> List[Tuple[Path, Dict[str, str]]]:
    paths = sorted(TEMPLATE_DIR.glob(TEMPLATE_GLOB))
    if not paths:
        raise ValueError(f"No real evidence input templates found in {TEMPLATE_DIR}")

    selected: List[Tuple[Path, Dict[str, str]]] = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Template must contain a JSON object: {path}")
        record = normalize_record(data)
        if evidence_id and record["evidence_id"] != evidence_id:
            continue
        selected.append((path, record))

    if evidence_id and not selected:
        raise ValueError(f"No template found for evidence_id={evidence_id}")
    return selected


def parse_vtt_timestamp_to_seconds(timestamp: str) -> int:
    cleaned = timestamp.replace(",", ".")
    main = cleaned.split(".", 1)[0]
    parts = main.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + int(seconds)
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    raise ValueError(f"Unsupported VTT timestamp: {timestamp}")


def format_template_timestamp(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"
    return f"{minutes:02d}:{remaining_seconds:02d}"


def clean_caption_text(value: str) -> str:
    without_tags = TAG_RE.sub("", value)
    without_entities = (
        without_tags.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&nbsp;", " ")
    )
    return WHITESPACE_RE.sub(" ", without_entities).strip()


def parse_webvtt(text: str) -> List[CaptionSegment]:
    segments: List[CaptionSegment] = []
    lines = text.splitlines()
    index = 0
    previous_text = ""

    while index < len(lines):
        line = lines[index].strip()
        match = TIMESTAMP_LINE_RE.match(line)
        if not match:
            index += 1
            continue

        start_seconds = parse_vtt_timestamp_to_seconds(match.group("start"))
        end_seconds = parse_vtt_timestamp_to_seconds(match.group("end"))
        index += 1

        caption_lines: List[str] = []
        while index < len(lines) and lines[index].strip():
            candidate = lines[index].strip()
            if not candidate.startswith(("NOTE", "STYLE", "WEBVTT")):
                cleaned = clean_caption_text(candidate)
                if cleaned:
                    caption_lines.append(cleaned)
            index += 1

        caption_text = clean_caption_text(" ".join(caption_lines))
        if caption_text and caption_text != previous_text:
            segments.append(
                CaptionSegment(
                    timestamp_start=format_template_timestamp(start_seconds),
                    timestamp_end=format_template_timestamp(end_seconds),
                    text=caption_text,
                )
            )
            previous_text = caption_text

    return segments


def select_candidate_segments(
    segments: List[CaptionSegment], max_segments: int = 12
) -> List[CaptionSegment]:
    if len(segments) <= max_segments:
        return segments
    return segments[:max_segments]


def build_candidate_fields(
    record: Dict[str, str], segments: List[CaptionSegment]
) -> Dict[str, str]:
    selected = select_candidate_segments(segments)
    if not selected:
        raise ValueError("No usable caption segments found")

    transcript_text = " ".join(segment.text for segment in selected).strip()
    longest_segment = max(selected, key=lambda segment: len(segment.text))
    case_relevance_note = record["case_relevance_note"].strip() or CASE_RELEVANCE_NOTES.get(
        record["case_id"],
        "Auto-collected evidence candidate. Human case relevance review required before approval.",
    )

    return {
        "transcript_text": transcript_text,
        "timestamp_start": selected[0].timestamp_start,
        "timestamp_end": selected[-1].timestamp_end,
        "quote_text": longest_segment.text,
        "speaker": record["speaker"].strip() or AUTO_SPEAKER,
        "context_summary": record["context_summary"].strip() or AUTO_CONTEXT_SUMMARY,
        "case_relevance_note": case_relevance_note,
        "reviewer": record["reviewer"].strip(),
        "reviewer_notes": record["reviewer_notes"].strip() or AUTO_REVIEWER_NOTES,
        "verification_status": "entered_pending_review",
    }


def ordered_record(record: Dict[str, str]) -> Dict[str, str]:
    return {field: record[field] for field in ALL_FIELDS}


def merge_candidate(record: Dict[str, str], candidate_fields: Dict[str, str]) -> Dict[str, str]:
    merged = dict(record)
    for field_name, value in candidate_fields.items():
        if field_name == "verification_status":
            merged[field_name] = "entered_pending_review"
        elif value:
            merged[field_name] = value
    merged["verification_status"] = "entered_pending_review"
    return merged


def find_yt_dlp() -> Optional[str]:
    return shutil.which("yt-dlp")


def run_subprocess(command: List[str], timeout_seconds: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_seconds,
    )


def collect_segments_with_yt_dlp(
    yt_dlp_path: str, url: str, timeout_seconds: int
) -> Tuple[List[CaptionSegment], str]:
    with tempfile.TemporaryDirectory(prefix="real-evidence-captions-") as temp_dir:
        output_template = str(Path(temp_dir) / "%(id)s.%(ext)s")
        subtitle_command = [
            yt_dlp_path,
            "--skip-download",
            "--write-auto-subs",
            "--write-subs",
            "--sub-langs",
            "en",
            "--sub-format",
            "vtt",
            "--output",
            output_template,
            url,
        ]
        subtitle_result = run_subprocess(subtitle_command, timeout_seconds)
        if subtitle_result.returncode != 0:
            metadata_command = [yt_dlp_path, "--skip-download", "--dump-json", url]
            metadata_result = run_subprocess(metadata_command, timeout_seconds)
            metadata_message = (
                metadata_result.stderr.strip()
                or metadata_result.stdout.strip()
                or "metadata unavailable"
            )
            return [], (
                "yt-dlp subtitle collection failed; metadata fallback result: "
                f"{metadata_message[:500]}"
            )

        segments: List[CaptionSegment] = []
        for vtt_path in sorted(Path(temp_dir).glob("*.vtt")):
            segments.extend(parse_webvtt(vtt_path.read_text(encoding="utf-8")))
        if not segments:
            return [], "yt-dlp completed but no usable English VTT captions were found"
        return segments, "candidate captions collected with yt-dlp"


def build_status_record(
    record: Dict[str, str],
    collection_status: str,
    message: str,
    candidate_fields: Optional[Dict[str, str]] = None,
    would_write_template: bool = False,
    backup_path: str = "",
) -> AutoCollectionRecord:
    if collection_status not in STATUSES:
        raise ValueError(f"Unsupported collection status: {collection_status}")
    candidate_fields = candidate_fields or {}
    if candidate_fields.get("verification_status") == "verified_for_approval_review":
        raise ValueError("Auto-collection must not set verified_for_approval_review")
    return AutoCollectionRecord(
        evidence_id=record["evidence_id"],
        case_id=record["case_id"],
        source_url=record["source_url"],
        collection_status=collection_status,
        message=message,
        candidate_available=collection_status == "candidate_collected",
        would_write_template=would_write_template,
        backup_path=backup_path,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        candidate_fields=candidate_fields,
    )


def collect_candidate_for_record(
    record: Dict[str, str],
    no_network: bool,
    timeout_seconds: int,
    yt_dlp_path: Optional[str] = None,
) -> AutoCollectionRecord:
    if no_network:
        return build_status_record(
            record,
            "network_disabled",
            "Network disabled by --no-network; human manual entry is required.",
        )

    yt_dlp = yt_dlp_path if yt_dlp_path is not None else find_yt_dlp()
    if not yt_dlp:
        return build_status_record(
            record,
            "yt_dlp_missing",
            "yt-dlp is not installed or not on PATH; human manual entry is required.",
        )

    try:
        segments, message = collect_segments_with_yt_dlp(
            yt_dlp, record["source_url"], timeout_seconds
        )
        if not segments:
            return build_status_record(record, "captions_unavailable", message)
        candidate_fields = build_candidate_fields(record, segments)
        return build_status_record(
            record,
            "candidate_collected",
            message,
            candidate_fields=candidate_fields,
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return build_status_record(
            record,
            "collection_failed",
            f"Collection failed without candidate approval: {type(exc).__name__}: {exc}",
        )


def write_template_candidate(
    path: Path, record: Dict[str, str], candidate_fields: Dict[str, str]
) -> str:
    backup_path = path.with_name(f"{path.name}.bak")
    shutil.copy2(path, backup_path)
    updated = merge_candidate(record, candidate_fields)
    path.write_text(
        json.dumps(ordered_record(updated), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return str(backup_path)


def write_outputs(
    records: List[AutoCollectionRecord],
    mode: str,
    write_count: int,
    backup_count: int,
) -> Dict[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at_utc": utc_now_iso(),
        "mode": mode,
        "selected_evidence_count": len(records),
        "candidate_count": sum(1 for record in records if record.candidate_available),
        "unavailable_count": sum(1 for record in records if not record.candidate_available),
        "write_count": write_count,
        "backup_count": backup_count,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
        "status_output": str(STATUS_OUTPUT),
        "summary_output": str(SUMMARY_OUTPUT),
    }
    status = {
        "metadata": {
            "generated_at_utc": utc_now_iso(),
            "mode": mode,
            "public_ready": False,
            "institutional_ready": False,
            "report_ready": False,
        },
        "records": [record.to_dict() for record in records],
    }
    STATUS_OUTPUT.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    SUMMARY_OUTPUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return {"status_output": str(STATUS_OUTPUT), "summary_output": str(SUMMARY_OUTPUT)}


def auto_collect_real_evidence(
    evidence_id: str = "",
    dry_run: bool = True,
    no_network: bool = False,
    timeout_seconds: int = 60,
) -> Dict[str, Any]:
    templates = load_templates(evidence_id)
    write_candidates = not dry_run
    records: List[AutoCollectionRecord] = []
    write_count = 0
    backup_count = 0

    for path, template_record in templates:
        result = collect_candidate_for_record(
            template_record,
            no_network=no_network,
            timeout_seconds=timeout_seconds,
        )
        if write_candidates and result.candidate_available:
            backup_path = write_template_candidate(
                path, template_record, result.candidate_fields
            )
            result.would_write_template = True
            result.backup_path = backup_path
            write_count += 1
            backup_count += 1
        elif result.candidate_available:
            result.would_write_template = write_candidates
        records.append(result)

    mode = "write-candidates" if write_candidates else "dry-run"
    outputs = write_outputs(records, mode, write_count, backup_count)
    return {
        "mode": mode,
        "selected_evidence_count": len(records),
        "candidate_count": sum(1 for record in records if record.candidate_available),
        "unavailable_count": sum(1 for record in records if not record.candidate_available),
        "write_count": write_count,
        "backup_count": backup_count,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
        "records": records,
        **outputs,
    }


def print_summary(summary: Dict[str, Any]) -> None:
    print("== Real Evidence Auto-Collection Helper v1 summary ==")
    print(f"Mode: {summary['mode']}")
    print(f"selected_evidence_count: {summary['selected_evidence_count']}")
    print(f"candidate_count: {summary['candidate_count']}")
    print(f"unavailable_count: {summary['unavailable_count']}")
    print(f"write_count: {summary['write_count']}")
    print(f"backup_count: {summary['backup_count']}")
    print(f"public_ready: {summary['public_ready']}")
    print(f"institutional_ready: {summary['institutional_ready']}")
    print(f"report_ready: {summary['report_ready']}")
    print(f"status_output: {summary['status_output']}")
    print(f"summary_output: {summary['summary_output']}")
    for record in summary["records"]:
        print()
        print(f"evidence_id: {record.evidence_id}")
        print(f"collection_status: {record.collection_status}")
        print(f"message: {record.message}")
        if record.candidate_available:
            print("verification_status: entered_pending_review")


def main() -> int:
    args = parse_args()
    if args.timeout_seconds <= 0:
        print("ERROR: --timeout-seconds must be positive", file=sys.stderr)
        return 1

    dry_run = True
    if args.write_candidates and not args.dry_run:
        dry_run = False

    try:
        summary = auto_collect_real_evidence(
            evidence_id=args.evidence_id or "",
            dry_run=dry_run,
            no_network=args.no_network,
            timeout_seconds=args.timeout_seconds,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
