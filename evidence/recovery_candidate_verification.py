"""
recovery_candidate_verification.py - Reachability diagnostics for recovery candidates.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import json
import socket
import urllib.error
import urllib.request

from evidence.source_recovery import (
    SourceRecoveryCandidateRecord,
    load_source_recovery_candidates,
    validate_source_recovery_candidate_record,
)


DEFAULT_RECOVERY_CANDIDATE_VERIFICATION_OUTPUT_DIR = Path(
    "outputs/recovery_candidate_verification"
)
DEFAULT_RECOVERY_CANDIDATE_VERIFICATION_STATUS_OUTPUT = (
    DEFAULT_RECOVERY_CANDIDATE_VERIFICATION_OUTPUT_DIR
    / "recovery_candidate_verification_status.json"
)
DEFAULT_RECOVERY_CANDIDATE_VERIFICATION_SUMMARY_OUTPUT = (
    DEFAULT_RECOVERY_CANDIDATE_VERIFICATION_OUTPUT_DIR
    / "recovery_candidate_verification_summary.json"
)

REACHABILITY_STATUSES = {
    "not_checked",
    "reachable",
    "unreachable",
    "blocked",
    "error",
}

CONTENT_STATUSES = {
    "not_checked",
    "candidate_content_found",
    "candidate_content_not_found",
    "requires_manual_review",
    "error",
}

VERIFICATION_STATUSES = {
    "candidate_unverified",
    "reachable_pending_manual_review",
    "blocked_unusable",
    "unreachable_unusable",
    "rejected",
}

FORBIDDEN_VERIFICATION_CLAIMS = (
    "approved_evidence: true",
    "public_ready: true",
    "institutional_ready: true",
    "report_ready: true",
    "verified_for_manual_review: true",
    "verified_for_approval_review",
    "approved evidence",
    "ready for public release",
    "ready for institutional release",
    "public-ready",
    "institution-ready",
    "final forensic report",
)


@dataclass
class RecoveryCandidateVerificationRecord:
    recovery_candidate_id: str
    original_evidence_id: str
    recovery_source_url: str
    recovery_source_type: str
    reachability_status: str
    content_status: str
    verification_status: str
    verified_for_manual_review: bool
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
            f"RecoveryCandidateVerificationRecord.{field_name} must be a "
            "non-empty string"
        )


def _reject_forbidden_claims(data: Dict[str, Any]) -> None:
    text = "\n".join(_string_values(data)).lower()
    for claim in FORBIDDEN_VERIFICATION_CLAIMS:
        if claim in text:
            raise ValueError(
                "RecoveryCandidateVerificationRecord contains prohibited "
                f"verification/readiness claim: {claim}"
            )


def validate_recovery_candidate_verification_record(record: Any) -> None:
    data = _as_dict(record)

    for field_name in (
        "recovery_candidate_id",
        "original_evidence_id",
        "recovery_source_url",
        "recovery_source_type",
        "reachability_status",
        "content_status",
        "verification_status",
        "notes",
    ):
        _require_nonempty_string(data, field_name)

    if data["reachability_status"] not in REACHABILITY_STATUSES:
        raise ValueError(
            "RecoveryCandidateVerificationRecord.reachability_status is "
            f"unsupported: {data['reachability_status']}"
        )
    if data["content_status"] not in CONTENT_STATUSES:
        raise ValueError(
            "RecoveryCandidateVerificationRecord.content_status is unsupported: "
            f"{data['content_status']}"
        )
    if data["verification_status"] not in VERIFICATION_STATUSES:
        raise ValueError(
            "RecoveryCandidateVerificationRecord.verification_status is "
            f"unsupported: {data['verification_status']}"
        )

    if data.get("verified_for_manual_review") is not False:
        raise ValueError(
            "RecoveryCandidateVerificationRecord.verified_for_manual_review "
            "must be false"
        )
    if data.get("approved_evidence") is not False:
        raise ValueError(
            "RecoveryCandidateVerificationRecord.approved_evidence must be false"
        )
    if data.get("public_ready") is not False:
        raise ValueError(
            "RecoveryCandidateVerificationRecord.public_ready must be false"
        )
    if data.get("institutional_ready") is not False:
        raise ValueError(
            "RecoveryCandidateVerificationRecord.institutional_ready must be false"
        )
    if data.get("report_ready") is not False:
        raise ValueError(
            "RecoveryCandidateVerificationRecord.report_ready must be false"
        )

    _reject_forbidden_claims(data)


def build_verification_record(
    candidate: SourceRecoveryCandidateRecord,
    reachability_status: str = "not_checked",
    content_status: str = "requires_manual_review",
    verification_status: str = "candidate_unverified",
    notes: str = "Candidate source requires human review before any use.",
) -> RecoveryCandidateVerificationRecord:
    validate_source_recovery_candidate_record(candidate)
    record = RecoveryCandidateVerificationRecord(
        recovery_candidate_id=candidate.recovery_candidate_id,
        original_evidence_id=candidate.original_evidence_id,
        recovery_source_url=candidate.recovery_source_url,
        recovery_source_type=candidate.recovery_source_type,
        reachability_status=reachability_status,
        content_status=content_status,
        verification_status=verification_status,
        verified_for_manual_review=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        notes=notes,
    )
    validate_recovery_candidate_verification_record(record)
    return record


def _is_candidate_content_type(content_type: str) -> bool:
    normalized = content_type.lower().split(";", 1)[0].strip()
    return (
        normalized.startswith("text/")
        or normalized in {"application/pdf", "application/json", "application/xml"}
        or normalized.endswith("+json")
        or normalized.endswith("+xml")
    )


def _request_url(
    url: str,
    method: str,
    timeout_seconds: int,
) -> Tuple[int, str, str]:
    headers = {
        "User-Agent": "recovery-candidate-verification-v1/1.0",
        "Accept": "text/html,application/xhtml+xml,application/pdf,text/plain,*/*;q=0.2",
    }
    if method == "GET":
        headers["Range"] = "bytes=0-4095"
    request = urllib.request.Request(url, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        status_code = int(response.getcode() or 0)
        content_type = response.headers.get("Content-Type", "")
        final_url = response.geturl()
        if method == "GET":
            response.read(4096)
        return status_code, content_type, final_url


def _network_status_from_response(
    status_code: int,
    content_type: str,
) -> Tuple[str, str, str, str]:
    if status_code in {401, 403, 451}:
        return (
            "blocked",
            "requires_manual_review",
            "blocked_unusable",
            f"HTTP {status_code}; candidate source is blocked or access-limited.",
        )
    if status_code in {404, 410}:
        return (
            "unreachable",
            "candidate_content_not_found",
            "unreachable_unusable",
            f"HTTP {status_code}; candidate source was not reachable.",
        )
    if 200 <= status_code < 400:
        if _is_candidate_content_type(content_type):
            return (
                "reachable",
                "candidate_content_found",
                "reachable_pending_manual_review",
                f"HTTP {status_code}; content-type {content_type or 'unknown'}. "
                "Candidate content requires human manual review.",
            )
        return (
            "reachable",
            "requires_manual_review",
            "candidate_unverified",
            f"HTTP {status_code}; content-type {content_type or 'unknown'} requires "
            "human manual review.",
        )
    return (
        "error",
        "error",
        "candidate_unverified",
        f"HTTP {status_code}; candidate source could not be classified.",
    )


def verify_candidate_reachability(
    candidate: SourceRecoveryCandidateRecord,
    no_network: bool = False,
    timeout_seconds: int = 10,
) -> RecoveryCandidateVerificationRecord:
    if no_network:
        return build_verification_record(
            candidate,
            reachability_status="not_checked",
            content_status="requires_manual_review",
            verification_status="candidate_unverified",
            notes="Network disabled; candidate source requires manual review.",
        )

    try:
        try:
            status_code, content_type, final_url = _request_url(
                candidate.recovery_source_url,
                method="HEAD",
                timeout_seconds=timeout_seconds,
            )
        except urllib.error.HTTPError as exc:
            if exc.code != 405:
                status_code = int(exc.code)
                content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
                final_url = candidate.recovery_source_url
            else:
                status_code, content_type, final_url = _request_url(
                    candidate.recovery_source_url,
                    method="GET",
                    timeout_seconds=timeout_seconds,
                )

        reachability_status, content_status, verification_status, notes = (
            _network_status_from_response(status_code, content_type)
        )
        if final_url and final_url != candidate.recovery_source_url:
            notes = f"{notes} Redirected to {final_url}."
        return build_verification_record(
            candidate,
            reachability_status=reachability_status,
            content_status=content_status,
            verification_status=verification_status,
            notes=notes,
        )
    except urllib.error.HTTPError as exc:
        reachability_status, content_status, verification_status, notes = (
            _network_status_from_response(exc.code, exc.headers.get("Content-Type", ""))
        )
        return build_verification_record(
            candidate,
            reachability_status=reachability_status,
            content_status=content_status,
            verification_status=verification_status,
            notes=notes,
        )
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        return build_verification_record(
            candidate,
            reachability_status="error",
            content_status="error",
            verification_status="candidate_unverified",
            notes=f"Network check failed without approval impact: {exc}",
        )


def summarize_verification_records(
    records: List[RecoveryCandidateVerificationRecord],
) -> Dict[str, Any]:
    for record in records:
        validate_recovery_candidate_verification_record(record)

    return {
        "generated_at_utc": utc_now_iso(),
        "total_candidates": len(records),
        "reachable_candidates": sum(
            1 for record in records if record.reachability_status == "reachable"
        ),
        "blocked_candidates": sum(
            1 for record in records if record.reachability_status == "blocked"
        ),
        "unreachable_candidates": sum(
            1 for record in records if record.reachability_status == "unreachable"
        ),
        "error_candidates": sum(
            1 for record in records if record.reachability_status == "error"
        ),
        "not_checked_candidates": sum(
            1 for record in records if record.reachability_status == "not_checked"
        ),
        "candidate_content_found": sum(
            1 for record in records if record.content_status == "candidate_content_found"
        ),
        "requires_manual_review": sum(
            1 for record in records if record.content_status == "requires_manual_review"
        ),
        "approved_evidence": 0,
        "verified_for_manual_review": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }


def write_verification_outputs(
    records: List[RecoveryCandidateVerificationRecord],
    output_dir: Path = DEFAULT_RECOVERY_CANDIDATE_VERIFICATION_OUTPUT_DIR,
) -> Dict[str, str]:
    for record in records:
        validate_recovery_candidate_verification_record(record)

    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / "recovery_candidate_verification_status.json"
    summary_path = output_dir / "recovery_candidate_verification_summary.json"
    summary = summarize_verification_records(records)
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


def verify_recovery_candidates(
    candidate_id: Optional[str] = None,
    no_network: bool = False,
    timeout_seconds: int = 10,
    output_dir: Path = DEFAULT_RECOVERY_CANDIDATE_VERIFICATION_OUTPUT_DIR,
) -> Dict[str, Any]:
    candidates = load_source_recovery_candidates()
    if candidate_id:
        candidates = [
            candidate
            for candidate in candidates
            if candidate.recovery_candidate_id == candidate_id
        ]
        if not candidates:
            raise ValueError(f"Unknown recovery candidate ID: {candidate_id}")

    records = [
        verify_candidate_reachability(
            candidate,
            no_network=no_network,
            timeout_seconds=timeout_seconds,
        )
        for candidate in candidates
    ]
    outputs = write_verification_outputs(records, output_dir=output_dir)
    summary = summarize_verification_records(records)
    summary.update(outputs)
    return summary
