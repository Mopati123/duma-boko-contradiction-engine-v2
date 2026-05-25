"""
health_fallback_source.py - Candidate-only fallback handling for VID_HEALTH_001.
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
from evidence.source_recovery import (
    SourceRecoveryCandidateRecord,
    load_source_recovery_candidates,
    validate_source_recovery_candidate_record,
)


DEFAULT_HEALTH_FALLBACK_SOURCE_OUTPUT_DIR = Path("outputs/health_fallback_source")
DEFAULT_HEALTH_FALLBACK_SOURCE_STATUS_OUTPUT = (
    DEFAULT_HEALTH_FALLBACK_SOURCE_OUTPUT_DIR / "health_fallback_source_status.json"
)
DEFAULT_HEALTH_FALLBACK_SOURCE_SUMMARY_OUTPUT = (
    DEFAULT_HEALTH_FALLBACK_SOURCE_OUTPUT_DIR / "health_fallback_source_summary.json"
)

HEALTH_EVIDENCE_ID = "VID_HEALTH_001"
BLOCKED_HEALTH_SELECTED_CANDIDATE_ID = "RECOVERY_VID_HEALTH_001_REUTERS"
PRIMARY_HEALTH_FALLBACK_CANDIDATE_ID = "RECOVERY_VID_HEALTH_001_AL_JAZEERA"
NEXT_HEALTH_FALLBACK_CANDIDATE_ID = (
    "RECOVERY_VID_HEALTH_001_BOTSWANA_YOUTH_36_TONNES"
)

FALLBACK_STATUSES = {
    "fallback_selected",
    "fallback_not_needed",
    "fallback_unavailable",
    "fallback_blocked",
    "fallback_error",
}

EXTRACTION_STATUSES = {
    "not_checked",
    "extracted_candidate",
    "extraction_unavailable",
    "blocked",
    "error",
}

VERIFICATION_STATUSES = {
    "not_checked",
    "verified_candidate_for_content_review",
    "blocked_pending_fallback",
    "extraction_unavailable",
    "rejected",
    "error",
}

CONTENT_REVIEW_STATUSES = {
    "not_checked",
    "keyword_match",
    "insufficient_content",
    "blocked_source",
    "requires_manual_review",
    "error",
}

HEALTH_FALLBACK_KEYWORDS = (
    "public health emergency",
    "medicine",
    "medicines",
    "medical supply",
    "medical supplies",
    "clinics",
    "hospitals",
    "shortage",
    "shortages",
    "supply chain",
    "Duma Boko",
)

FORBIDDEN_FALLBACK_CLAIMS = (
    "verified_for_approval_review",
    "approved_evidence: true",
    "public_ready: true",
    "institutional_ready: true",
    "report_ready: true",
    "approved evidence",
    "ready for public release",
    "ready for institutional release",
    "public-ready",
    "institution-ready",
    "final forensic report",
)


@dataclass
class HealthFallbackSourceRecord:
    original_evidence_id: str
    blocked_selected_candidate_id: str
    fallback_candidate_id: str
    fallback_source_url: str
    fallback_source_type: str
    fallback_reason: str
    fallback_status: str
    extraction_status: str
    verification_status: str
    content_review_status: str
    extracted_text_candidate: str
    extracted_quote_candidate: str
    verified_for_content_review: bool
    approved_evidence: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    requires_manual_review: bool
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
            f"HealthFallbackSourceRecord.{field_name} must be a non-empty string"
        )


def _reject_forbidden_claims(data: Dict[str, Any]) -> None:
    if "verified_for_approval_review" in data:
        raise ValueError(
            "HealthFallbackSourceRecord must not contain verified_for_approval_review"
        )

    text = "\n".join(_string_values(data)).lower()
    for claim in FORBIDDEN_FALLBACK_CLAIMS:
        if claim in text:
            raise ValueError(
                "HealthFallbackSourceRecord contains prohibited approval/readiness "
                f"claim: {claim}"
            )


def validate_health_fallback_source_record(record: Any) -> None:
    data = _as_dict(record)

    for field_name in (
        "original_evidence_id",
        "blocked_selected_candidate_id",
        "fallback_candidate_id",
        "fallback_source_url",
        "fallback_source_type",
        "fallback_reason",
        "fallback_status",
        "extraction_status",
        "verification_status",
        "content_review_status",
        "notes",
    ):
        _require_nonempty_string(data, field_name)

    if data["original_evidence_id"] != HEALTH_EVIDENCE_ID:
        raise ValueError(
            "HealthFallbackSourceRecord.original_evidence_id must be "
            f"{HEALTH_EVIDENCE_ID}"
        )
    if data["blocked_selected_candidate_id"] != BLOCKED_HEALTH_SELECTED_CANDIDATE_ID:
        raise ValueError(
            "HealthFallbackSourceRecord.blocked_selected_candidate_id must be "
            f"{BLOCKED_HEALTH_SELECTED_CANDIDATE_ID}"
        )

    if data["fallback_status"] not in FALLBACK_STATUSES:
        raise ValueError(
            "HealthFallbackSourceRecord.fallback_status is unsupported: "
            f"{data['fallback_status']}"
        )
    if data["extraction_status"] not in EXTRACTION_STATUSES:
        raise ValueError(
            "HealthFallbackSourceRecord.extraction_status is unsupported: "
            f"{data['extraction_status']}"
        )
    if data["verification_status"] not in VERIFICATION_STATUSES:
        raise ValueError(
            "HealthFallbackSourceRecord.verification_status is unsupported: "
            f"{data['verification_status']}"
        )
    if data["content_review_status"] not in CONTENT_REVIEW_STATUSES:
        raise ValueError(
            "HealthFallbackSourceRecord.content_review_status is unsupported: "
            f"{data['content_review_status']}"
        )

    if data.get("requires_manual_review") is not True:
        raise ValueError(
            "HealthFallbackSourceRecord.requires_manual_review must be true"
        )
    if data.get("approved_evidence") is not False:
        raise ValueError("HealthFallbackSourceRecord.approved_evidence must be false")
    if data.get("public_ready") is not False:
        raise ValueError("HealthFallbackSourceRecord.public_ready must be false")
    if data.get("institutional_ready") is not False:
        raise ValueError(
            "HealthFallbackSourceRecord.institutional_ready must be false"
        )
    if data.get("report_ready") is not False:
        raise ValueError("HealthFallbackSourceRecord.report_ready must be false")

    if (
        data.get("verified_for_content_review") is True
        and data["verification_status"] != "verified_candidate_for_content_review"
    ):
        raise ValueError(
            "HealthFallbackSourceRecord.verified_for_content_review requires "
            "verification_status=verified_candidate_for_content_review"
        )

    if data["extraction_status"] == "extracted_candidate":
        _require_nonempty_string(data, "extracted_text_candidate")
        _require_nonempty_string(data, "extracted_quote_candidate")

    _reject_forbidden_claims(data)


def _candidate_lookup(
    candidates: List[SourceRecoveryCandidateRecord],
) -> Dict[str, SourceRecoveryCandidateRecord]:
    lookup: Dict[str, SourceRecoveryCandidateRecord] = {}
    for candidate in candidates:
        validate_source_recovery_candidate_record(candidate)
        lookup[candidate.recovery_candidate_id] = candidate
    return lookup


def _selected_health_source(
    selected_sources: List[SelectedRecoverySourceRecord],
) -> SelectedRecoverySourceRecord:
    health_sources = [
        source
        for source in selected_sources
        if source.original_evidence_id == HEALTH_EVIDENCE_ID
    ]
    if len(health_sources) != 1:
        raise ValueError("Expected exactly one selected health recovery source")

    selected = health_sources[0]
    validate_selected_recovery_source_record(selected)
    if selected.selected_recovery_candidate_id != BLOCKED_HEALTH_SELECTED_CANDIDATE_ID:
        raise ValueError(
            "Health fallback requires Reuters to remain the selected blocked source"
        )
    return selected


def select_health_fallback_candidate(
    candidates: Optional[List[SourceRecoveryCandidateRecord]] = None,
    selected_sources: Optional[List[SelectedRecoverySourceRecord]] = None,
) -> Tuple[
    SelectedRecoverySourceRecord,
    SourceRecoveryCandidateRecord,
    SourceRecoveryCandidateRecord,
]:
    candidate_records = candidates or load_source_recovery_candidates()
    selected_records = selected_sources or load_selected_recovery_sources(
        evidence_id=HEALTH_EVIDENCE_ID,
        candidates=candidate_records,
    )
    selected = _selected_health_source(selected_records)
    lookup = _candidate_lookup(candidate_records)

    if PRIMARY_HEALTH_FALLBACK_CANDIDATE_ID not in lookup:
        raise ValueError(
            "Missing primary health fallback candidate: "
            f"{PRIMARY_HEALTH_FALLBACK_CANDIDATE_ID}"
        )
    if NEXT_HEALTH_FALLBACK_CANDIDATE_ID not in lookup:
        raise ValueError(
            "Missing next health fallback candidate: "
            f"{NEXT_HEALTH_FALLBACK_CANDIDATE_ID}"
        )

    fallback = lookup[PRIMARY_HEALTH_FALLBACK_CANDIDATE_ID]
    next_fallback = lookup[NEXT_HEALTH_FALLBACK_CANDIDATE_ID]
    for candidate in (fallback, next_fallback):
        if candidate.original_evidence_id != HEALTH_EVIDENCE_ID:
            raise ValueError("Health fallback candidates must belong to VID_HEALTH_001")

    return selected, fallback, next_fallback


def build_health_fallback_record(
    selected_source: SelectedRecoverySourceRecord,
    fallback_candidate: SourceRecoveryCandidateRecord,
    next_fallback_candidate: SourceRecoveryCandidateRecord,
    fallback_status: str = "fallback_selected",
    extraction_status: str = "not_checked",
    verification_status: str = "not_checked",
    content_review_status: str = "not_checked",
    extracted_text_candidate: str = "",
    extracted_quote_candidate: str = "",
    verified_for_content_review: bool = False,
    notes: str = "Network disabled; fallback source requires manual content review.",
) -> HealthFallbackSourceRecord:
    validate_selected_recovery_source_record(selected_source)
    validate_source_recovery_candidate_record(fallback_candidate)
    validate_source_recovery_candidate_record(next_fallback_candidate)

    record = HealthFallbackSourceRecord(
        original_evidence_id=HEALTH_EVIDENCE_ID,
        blocked_selected_candidate_id=selected_source.selected_recovery_candidate_id,
        fallback_candidate_id=fallback_candidate.recovery_candidate_id,
        fallback_source_url=fallback_candidate.recovery_source_url,
        fallback_source_type=fallback_candidate.recovery_source_type,
        fallback_reason=(
            "Reuters selected source is blocked for source-content extraction; "
            "Al Jazeera is the first configured fallback for candidate-only review."
        ),
        fallback_status=fallback_status,
        extraction_status=extraction_status,
        verification_status=verification_status,
        content_review_status=content_review_status,
        extracted_text_candidate=extracted_text_candidate,
        extracted_quote_candidate=extracted_quote_candidate,
        verified_for_content_review=verified_for_content_review,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            f"{notes} Next fallback if this source remains unusable: "
            f"{next_fallback_candidate.recovery_candidate_id}."
        ),
    )
    validate_health_fallback_source_record(record)
    return record


def _request_text(
    url: str,
    timeout_seconds: int,
    max_bytes: int = 262144,
) -> Tuple[int, str, str, str]:
    headers = {
        "User-Agent": "health-fallback-source-v1/1.0",
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


def _contains_keyword(text: str) -> bool:
    normalized = text.lower()
    return any(keyword.lower() in normalized for keyword in HEALTH_FALLBACK_KEYWORDS)


def _truncate(text: str, max_chars: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _quote_from_block(block: str) -> str:
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", block)
        if sentence.strip()
    ]
    matching_sentences = [sentence for sentence in sentences if _contains_keyword(sentence)]
    if matching_sentences:
        return _truncate(" ".join(matching_sentences[:2]), 500)
    return _truncate(block, 500)


def extract_health_fallback_candidate_text(html_text: str) -> Tuple[str, str]:
    blocks = _html_to_blocks(html_text)
    matching_blocks = [block for block in blocks if _contains_keyword(block)]
    if not matching_blocks:
        return "", ""

    selected_block = max(matching_blocks, key=lambda block: min(len(block), 1200))
    return _truncate(selected_block, 1200), _quote_from_block(selected_block)


def handle_health_fallback_candidate(
    no_network: bool = False,
    timeout_seconds: int = 10,
) -> HealthFallbackSourceRecord:
    selected_source, fallback_candidate, next_fallback_candidate = (
        select_health_fallback_candidate()
    )
    if no_network:
        return build_health_fallback_record(
            selected_source,
            fallback_candidate,
            next_fallback_candidate,
        )

    try:
        status_code, content_type, html_text, final_url = _request_text(
            fallback_candidate.recovery_source_url,
            timeout_seconds=timeout_seconds,
        )
        if status_code in {401, 403, 451}:
            return build_health_fallback_record(
                selected_source,
                fallback_candidate,
                next_fallback_candidate,
                fallback_status="fallback_blocked",
                extraction_status="blocked",
                verification_status="blocked_pending_fallback",
                content_review_status="blocked_source",
                notes=f"HTTP {status_code}; fallback source is blocked or access-limited.",
            )
        if status_code in {404, 410}:
            return build_health_fallback_record(
                selected_source,
                fallback_candidate,
                next_fallback_candidate,
                fallback_status="fallback_unavailable",
                extraction_status="extraction_unavailable",
                verification_status="extraction_unavailable",
                content_review_status="insufficient_content",
                notes=f"HTTP {status_code}; fallback source was not reachable.",
            )
        if not 200 <= status_code < 400:
            return build_health_fallback_record(
                selected_source,
                fallback_candidate,
                next_fallback_candidate,
                fallback_status="fallback_error",
                extraction_status="error",
                verification_status="error",
                content_review_status="error",
                notes=f"HTTP {status_code}; fallback extraction failed.",
            )
        if not _is_text_like(content_type):
            return build_health_fallback_record(
                selected_source,
                fallback_candidate,
                next_fallback_candidate,
                fallback_status="fallback_unavailable",
                extraction_status="extraction_unavailable",
                verification_status="extraction_unavailable",
                content_review_status="insufficient_content",
                notes=(
                    f"HTTP {status_code}; content-type {content_type or 'unknown'} "
                    "is not text-like enough for candidate extraction."
                ),
            )

        text_candidate, quote_candidate = extract_health_fallback_candidate_text(html_text)
        redirect_note = ""
        if final_url and final_url != fallback_candidate.recovery_source_url:
            redirect_note = f" Redirected to {final_url}."
        if text_candidate:
            return build_health_fallback_record(
                selected_source,
                fallback_candidate,
                next_fallback_candidate,
                fallback_status="fallback_selected",
                extraction_status="extracted_candidate",
                verification_status="verified_candidate_for_content_review",
                content_review_status="keyword_match",
                extracted_text_candidate=text_candidate,
                extracted_quote_candidate=quote_candidate,
                verified_for_content_review=True,
                notes=(
                    f"HTTP {status_code}; health fallback keyword candidate extracted. "
                    f"Human review required before use.{redirect_note}"
                ),
            )

        return build_health_fallback_record(
            selected_source,
            fallback_candidate,
            next_fallback_candidate,
            fallback_status="fallback_unavailable",
            extraction_status="extraction_unavailable",
            verification_status="extraction_unavailable",
            content_review_status="insufficient_content",
            notes=(
                f"HTTP {status_code}; fallback source reachable but no configured "
                f"health keyword candidate was found.{redirect_note}"
            ),
        )
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403, 451}:
            return build_health_fallback_record(
                selected_source,
                fallback_candidate,
                next_fallback_candidate,
                fallback_status="fallback_blocked",
                extraction_status="blocked",
                verification_status="blocked_pending_fallback",
                content_review_status="blocked_source",
                notes=f"HTTP {exc.code}; fallback source is blocked or access-limited.",
            )
        if exc.code in {404, 410}:
            return build_health_fallback_record(
                selected_source,
                fallback_candidate,
                next_fallback_candidate,
                fallback_status="fallback_unavailable",
                extraction_status="extraction_unavailable",
                verification_status="extraction_unavailable",
                content_review_status="insufficient_content",
                notes=f"HTTP {exc.code}; fallback source was not reachable.",
            )
        return build_health_fallback_record(
            selected_source,
            fallback_candidate,
            next_fallback_candidate,
            fallback_status="fallback_error",
            extraction_status="error",
            verification_status="error",
            content_review_status="error",
            notes=f"HTTP {exc.code}; fallback extraction could not be classified.",
        )
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        return build_health_fallback_record(
            selected_source,
            fallback_candidate,
            next_fallback_candidate,
            fallback_status="fallback_error",
            extraction_status="error",
            verification_status="error",
            content_review_status="error",
            notes=f"Network fallback extraction failed without approval impact: {exc}",
        )


def summarize_health_fallback_records(
    records: List[HealthFallbackSourceRecord],
) -> Dict[str, Any]:
    for record in records:
        validate_health_fallback_source_record(record)

    return {
        "generated_at_utc": utc_now_iso(),
        "total_records": len(records),
        "fallback_selected_count": sum(
            1 for record in records if record.fallback_status == "fallback_selected"
        ),
        "fallback_blocked_count": sum(
            1 for record in records if record.fallback_status == "fallback_blocked"
        ),
        "fallback_unavailable_count": sum(
            1
            for record in records
            if record.fallback_status == "fallback_unavailable"
        ),
        "fallback_error_count": sum(
            1 for record in records if record.fallback_status == "fallback_error"
        ),
        "extracted_candidate_count": sum(
            1 for record in records if record.extraction_status == "extracted_candidate"
        ),
        "not_checked_count": sum(
            1 for record in records if record.extraction_status == "not_checked"
        ),
        "verified_candidate_for_content_review_count": sum(
            1
            for record in records
            if record.verification_status == "verified_candidate_for_content_review"
        ),
        "verified_for_content_review_count": sum(
            1 for record in records if record.verified_for_content_review
        ),
        "requires_manual_review_count": sum(
            1 for record in records if record.requires_manual_review
        ),
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }


def write_health_fallback_outputs(
    records: List[HealthFallbackSourceRecord],
    output_dir: Path = DEFAULT_HEALTH_FALLBACK_SOURCE_OUTPUT_DIR,
) -> Dict[str, str]:
    for record in records:
        validate_health_fallback_source_record(record)

    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / "health_fallback_source_status.json"
    summary_path = output_dir / "health_fallback_source_summary.json"
    summary = summarize_health_fallback_records(records)
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


def handle_health_fallback_source(
    no_network: bool = False,
    timeout_seconds: int = 10,
    output_dir: Path = DEFAULT_HEALTH_FALLBACK_SOURCE_OUTPUT_DIR,
) -> Dict[str, Any]:
    record = handle_health_fallback_candidate(
        no_network=no_network,
        timeout_seconds=timeout_seconds,
    )
    records = [record]
    outputs = write_health_fallback_outputs(records, output_dir=output_dir)
    summary = summarize_health_fallback_records(records)
    summary["fallback_candidate_id"] = record.fallback_candidate_id
    summary["fallback_extraction_status"] = record.extraction_status
    summary["fallback_verification_status"] = record.verification_status
    summary.update(outputs)
    return summary
