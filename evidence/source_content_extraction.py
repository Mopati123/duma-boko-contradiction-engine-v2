"""
source_content_extraction.py - Candidate-only text extraction for selected sources.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import json
import re
import socket
import urllib.error
import urllib.request

from evidence.selected_recovery_source import (
    SelectedRecoverySourceRecord,
    load_selected_recovery_sources,
    validate_selected_recovery_source_record,
)


DEFAULT_SOURCE_CONTENT_EXTRACTION_OUTPUT_DIR = Path(
    "outputs/source_content_extraction"
)
DEFAULT_SOURCE_CONTENT_EXTRACTION_STATUS_OUTPUT = (
    DEFAULT_SOURCE_CONTENT_EXTRACTION_OUTPUT_DIR
    / "source_content_extraction_status.json"
)
DEFAULT_SOURCE_CONTENT_EXTRACTION_SUMMARY_OUTPUT = (
    DEFAULT_SOURCE_CONTENT_EXTRACTION_OUTPUT_DIR
    / "source_content_extraction_summary.json"
)

EXTRACTION_STATUSES = {
    "not_checked",
    "extracted_candidate",
    "extraction_unavailable",
    "blocked",
    "error",
}

CONTENT_SOURCE_STATUSES = {
    "not_checked",
    "source_reachable",
    "source_unreachable",
    "source_blocked",
    "source_error",
}

KEYWORDS_BY_EVIDENCE_ID = {
    "VID_JOBS_001": (
        "450,000",
        "500,000",
        "jobs",
        "employment",
        "manifesto",
    ),
    "VID_HEALTH_001": (
        "public health emergency",
        "medicine",
        "medical supply chain",
        "clinics",
        "hospitals",
        "shortage",
    ),
}

FORBIDDEN_EXTRACTION_CLAIMS = (
    "approved_evidence: true",
    "public_ready: true",
    "institutional_ready: true",
    "report_ready: true",
    "verified_for_manual_review",
    "verified_for_approval_review",
    "approved evidence",
    "ready for public release",
    "ready for institutional release",
    "public-ready",
    "institution-ready",
    "final forensic report",
)


@dataclass
class SourceContentExtractionRecord:
    original_evidence_id: str
    selected_recovery_candidate_id: str
    source_url: str
    extraction_status: str
    content_source_status: str
    extracted_text_candidate: str
    extracted_quote_candidate: str
    extraction_method: str
    requires_manual_review: bool
    approved_evidence: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
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


def _string_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _string_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _string_values(item)


def _require_nonempty_string(data: Dict[str, Any], field_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"SourceContentExtractionRecord.{field_name} must be a non-empty string"
        )


def _reject_forbidden_claims(data: Dict[str, Any]) -> None:
    for field_name in ("verified_for_manual_review", "verified_for_approval_review"):
        if field_name in data:
            raise ValueError(
                "SourceContentExtractionRecord must not contain verification field: "
                f"{field_name}"
            )

    text = "\n".join(_string_values(data)).lower()
    for claim in FORBIDDEN_EXTRACTION_CLAIMS:
        if claim in text:
            raise ValueError(
                "SourceContentExtractionRecord contains prohibited approval/readiness "
                f"claim: {claim}"
            )


def validate_source_content_extraction_record(record: Any) -> None:
    data = _as_dict(record)

    for field_name in (
        "original_evidence_id",
        "selected_recovery_candidate_id",
        "source_url",
        "extraction_status",
        "content_source_status",
        "extraction_method",
        "notes",
    ):
        _require_nonempty_string(data, field_name)

    if data["extraction_status"] not in EXTRACTION_STATUSES:
        raise ValueError(
            "SourceContentExtractionRecord.extraction_status is unsupported: "
            f"{data['extraction_status']}"
        )
    if data["content_source_status"] not in CONTENT_SOURCE_STATUSES:
        raise ValueError(
            "SourceContentExtractionRecord.content_source_status is unsupported: "
            f"{data['content_source_status']}"
        )

    if data.get("requires_manual_review") is not True:
        raise ValueError(
            "SourceContentExtractionRecord.requires_manual_review must be true"
        )
    if data.get("approved_evidence") is not False:
        raise ValueError("SourceContentExtractionRecord.approved_evidence must be false")
    if data.get("public_ready") is not False:
        raise ValueError("SourceContentExtractionRecord.public_ready must be false")
    if data.get("institutional_ready") is not False:
        raise ValueError(
            "SourceContentExtractionRecord.institutional_ready must be false"
        )
    if data.get("report_ready") is not False:
        raise ValueError("SourceContentExtractionRecord.report_ready must be false")

    if data["extraction_status"] == "extracted_candidate":
        _require_nonempty_string(data, "extracted_text_candidate")
        _require_nonempty_string(data, "extracted_quote_candidate")

    _reject_forbidden_claims(data)


def build_extraction_record(
    selected_source: SelectedRecoverySourceRecord,
    extraction_status: str = "not_checked",
    content_source_status: str = "not_checked",
    extracted_text_candidate: str = "",
    extracted_quote_candidate: str = "",
    extraction_method: str = "no_network",
    notes: str = "Network disabled; selected source requires manual content review.",
) -> SourceContentExtractionRecord:
    validate_selected_recovery_source_record(selected_source)
    record = SourceContentExtractionRecord(
        original_evidence_id=selected_source.original_evidence_id,
        selected_recovery_candidate_id=selected_source.selected_recovery_candidate_id,
        source_url=selected_source.selected_source_url,
        extraction_status=extraction_status,
        content_source_status=content_source_status,
        extracted_text_candidate=extracted_text_candidate,
        extracted_quote_candidate=extracted_quote_candidate,
        extraction_method=extraction_method,
        requires_manual_review=True,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        notes=notes,
    )
    validate_source_content_extraction_record(record)
    return record


def _request_text(
    url: str,
    timeout_seconds: int,
    max_bytes: int = 262144,
) -> Tuple[int, str, str, str]:
    headers = {
        "User-Agent": "source-content-extraction-v1/1.0",
        "Accept": "text/html,application/xhtml+xml,text/plain,*/*;q=0.2",
    }
    request = urllib.request.Request(url, method="GET", headers=headers)
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        status_code = int(response.getcode() or 0)
        content_type = response.headers.get("Content-Type", "")
        final_url = response.geturl()
        raw = response.read(max_bytes)
    charset = "utf-8"
    match = re.search(r"charset=([A-Za-z0-9._-]+)", content_type)
    if match:
        charset = match.group(1)
    return status_code, content_type, raw.decode(charset, errors="replace"), final_url


def _is_text_like(content_type: str) -> bool:
    normalized = content_type.lower().split(";", 1)[0].strip()
    return (
        normalized.startswith("text/")
        or normalized in {"application/xhtml+xml", "application/xml", "application/json"}
        or normalized.endswith("+xml")
        or normalized.endswith("+json")
        or not normalized
    )


def _html_to_blocks(html_text: str) -> List[str]:
    without_scripts = re.sub(
        r"(?is)<(script|style|noscript).*?>.*?</\1>",
        " ",
        html_text,
    )
    with_breaks = re.sub(
        r"(?i)</?(p|div|li|br|h[1-6]|section|article|tr|td|th)[^>]*>",
        "\n",
        without_scripts,
    )
    without_tags = re.sub(r"(?s)<[^>]+>", " ", with_breaks)
    text = unescape(without_tags)
    blocks: List[str] = []
    for line in text.splitlines():
        normalized = " ".join(line.split())
        if normalized:
            blocks.append(normalized)
    return blocks


def _contains_keyword(text: str, keywords: Iterable[str]) -> bool:
    normalized = text.lower()
    return any(keyword.lower() in normalized for keyword in keywords)


def _truncate(text: str, max_chars: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _quote_from_block(block: str, keywords: Iterable[str]) -> str:
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", block)
        if sentence.strip()
    ]
    matching_sentences = [
        sentence for sentence in sentences if _contains_keyword(sentence, keywords)
    ]
    if matching_sentences:
        return _truncate(" ".join(matching_sentences[:2]), 500)
    return _truncate(block, 500)


def extract_candidate_text(
    original_evidence_id: str,
    html_text: str,
) -> Tuple[str, str]:
    keywords = KEYWORDS_BY_EVIDENCE_ID.get(original_evidence_id, ())
    blocks = _html_to_blocks(html_text)
    matching_blocks = [block for block in blocks if _contains_keyword(block, keywords)]
    if not matching_blocks:
        return "", ""

    selected_block = max(matching_blocks, key=lambda block: min(len(block), 1200))
    text_candidate = _truncate(selected_block, 1200)
    quote_candidate = _quote_from_block(selected_block, keywords)
    return text_candidate, quote_candidate


def _record_from_http_error(
    selected_source: SelectedRecoverySourceRecord,
    exc: urllib.error.HTTPError,
) -> SourceContentExtractionRecord:
    if exc.code in {401, 403, 451}:
        return build_extraction_record(
            selected_source,
            extraction_status="blocked",
            content_source_status="source_blocked",
            extraction_method="stdlib_http_get",
            notes=f"HTTP {exc.code}; source is blocked or access-limited.",
        )
    if exc.code in {404, 410}:
        return build_extraction_record(
            selected_source,
            extraction_status="extraction_unavailable",
            content_source_status="source_unreachable",
            extraction_method="stdlib_http_get",
            notes=f"HTTP {exc.code}; source was not reachable.",
        )
    return build_extraction_record(
        selected_source,
        extraction_status="error",
        content_source_status="source_error",
        extraction_method="stdlib_http_get",
        notes=f"HTTP {exc.code}; source content extraction could not be classified.",
    )


def extract_content_for_selected_source(
    selected_source: SelectedRecoverySourceRecord,
    no_network: bool = False,
    timeout_seconds: int = 10,
) -> SourceContentExtractionRecord:
    validate_selected_recovery_source_record(selected_source)
    if no_network:
        return build_extraction_record(selected_source)

    try:
        status_code, content_type, html_text, final_url = _request_text(
            selected_source.selected_source_url,
            timeout_seconds=timeout_seconds,
        )
        if status_code in {401, 403, 451}:
            return build_extraction_record(
                selected_source,
                extraction_status="blocked",
                content_source_status="source_blocked",
                extraction_method="stdlib_http_get",
                notes=f"HTTP {status_code}; source is blocked or access-limited.",
            )
        if status_code in {404, 410}:
            return build_extraction_record(
                selected_source,
                extraction_status="extraction_unavailable",
                content_source_status="source_unreachable",
                extraction_method="stdlib_http_get",
                notes=f"HTTP {status_code}; source was not reachable.",
            )
        if not 200 <= status_code < 400:
            return build_extraction_record(
                selected_source,
                extraction_status="error",
                content_source_status="source_error",
                extraction_method="stdlib_http_get",
                notes=f"HTTP {status_code}; source content extraction failed.",
            )
        if not _is_text_like(content_type):
            return build_extraction_record(
                selected_source,
                extraction_status="extraction_unavailable",
                content_source_status="source_reachable",
                extraction_method="stdlib_http_get",
                notes=(
                    f"HTTP {status_code}; content-type {content_type or 'unknown'} "
                    "is not text-like enough for candidate extraction."
                ),
            )

        text_candidate, quote_candidate = extract_candidate_text(
            selected_source.original_evidence_id,
            html_text,
        )
        redirect_note = ""
        if final_url and final_url != selected_source.selected_source_url:
            redirect_note = f" Redirected to {final_url}."
        if text_candidate:
            return build_extraction_record(
                selected_source,
                extraction_status="extracted_candidate",
                content_source_status="source_reachable",
                extracted_text_candidate=text_candidate,
                extracted_quote_candidate=quote_candidate,
                extraction_method="stdlib_http_get_keyword_snippet",
                notes=(
                    f"HTTP {status_code}; keyword candidate extracted. "
                    f"Human review required before use.{redirect_note}"
                ),
            )

        return build_extraction_record(
            selected_source,
            extraction_status="extraction_unavailable",
            content_source_status="source_reachable",
            extraction_method="stdlib_http_get_keyword_snippet",
            notes=(
                f"HTTP {status_code}; selected source reachable but no configured "
                f"keyword candidate was found.{redirect_note}"
            ),
        )
    except urllib.error.HTTPError as exc:
        return _record_from_http_error(selected_source, exc)
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        return build_extraction_record(
            selected_source,
            extraction_status="error",
            content_source_status="source_error",
            extraction_method="stdlib_http_get",
            notes=f"Network extraction failed without approval impact: {exc}",
        )


def summarize_extraction_records(
    records: List[SourceContentExtractionRecord],
) -> Dict[str, Any]:
    for record in records:
        validate_source_content_extraction_record(record)

    return {
        "generated_at_utc": utc_now_iso(),
        "total_sources": len(records),
        "extracted_candidate_count": sum(
            1 for record in records if record.extraction_status == "extracted_candidate"
        ),
        "extraction_unavailable_count": sum(
            1
            for record in records
            if record.extraction_status == "extraction_unavailable"
        ),
        "blocked_count": sum(
            1 for record in records if record.extraction_status == "blocked"
        ),
        "error_count": sum(
            1 for record in records if record.extraction_status == "error"
        ),
        "not_checked_count": sum(
            1 for record in records if record.extraction_status == "not_checked"
        ),
        "requires_manual_review_count": sum(
            1 for record in records if record.requires_manual_review
        ),
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }


def write_extraction_outputs(
    records: List[SourceContentExtractionRecord],
    output_dir: Path = DEFAULT_SOURCE_CONTENT_EXTRACTION_OUTPUT_DIR,
) -> Dict[str, str]:
    for record in records:
        validate_source_content_extraction_record(record)

    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / "source_content_extraction_status.json"
    summary_path = output_dir / "source_content_extraction_summary.json"
    summary = summarize_extraction_records(records)
    summary["status_output"] = str(status_path)
    summary["summary_output"] = str(summary_path)

    status_payload = {
        "metadata": {
            "generated_at_utc": summary["generated_at_utc"],
            "public_ready": False,
            "institutional_ready": False,
            "report_ready": False,
        },
        "records": [record.to_dict() for record in records],
    }

    status_path.write_text(json.dumps(status_payload, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return {"status_output": str(status_path), "summary_output": str(summary_path)}


def extract_selected_source_content(
    evidence_id: Optional[str] = None,
    no_network: bool = False,
    timeout_seconds: int = 10,
    output_dir: Path = DEFAULT_SOURCE_CONTENT_EXTRACTION_OUTPUT_DIR,
) -> Dict[str, Any]:
    selected_sources = load_selected_recovery_sources(evidence_id=evidence_id)
    records = [
        extract_content_for_selected_source(
            selected_source,
            no_network=no_network,
            timeout_seconds=timeout_seconds,
        )
        for selected_source in selected_sources
    ]
    outputs = write_extraction_outputs(records, output_dir=output_dir)
    summary = summarize_extraction_records(records)
    summary.update(outputs)
    return summary
