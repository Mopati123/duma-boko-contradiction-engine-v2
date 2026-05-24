"""
final_approved_packet.py - Conservative final approved evidence packet checks.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List
import json

from evidence.evidence_schema import save_json
from evidence.real_evidence_approval import (
    DEFAULT_REAL_EVIDENCE_APPROVAL_RECORDS_OUTPUT,
    approve_real_evidence_dry_run,
    validate_real_evidence_approval_record,
)
from evidence.release_policy import check_release_policy_dry_run
from evidence.release_readiness import check_release_readiness_dry_run


DEFAULT_FINAL_APPROVED_PACKET_DIR = Path("outputs/final_approved_packet")
DEFAULT_FINAL_APPROVED_PACKET_RECORD = (
    DEFAULT_FINAL_APPROVED_PACKET_DIR / "final_approved_packet_record.json"
)
DEFAULT_FINAL_APPROVED_PACKET_SUMMARY = (
    DEFAULT_FINAL_APPROVED_PACKET_DIR / "final_approved_packet_summary.json"
)

PACKET_STATUSES = {
    "blocked_no_approved_evidence",
    "blocked_release_not_authorized",
    "packet_candidate_pending_release",
    "approved_packet_candidate",
}

BLOCKED_PACKET_STATUSES = {
    "blocked_no_approved_evidence",
    "blocked_release_not_authorized",
}

DRY_RUN_BLOCKER_REASONS = [
    "no approved evidence candidates",
    "real evidence approval required",
    "release readiness remains blocked",
    "public release authorization absent",
    "institutional release authorization absent",
]

FORBIDDEN_PACKET_CLAIMS = (
    "public_ready: true",
    "institutional_ready: true",
    "report_ready: true",
    "ready for public release",
    "ready for institutional release",
    "public-ready",
    "institution-ready",
    "institution ready",
    "validated public evidence",
    "final forensic report",
)


@dataclass
class FinalApprovedEvidencePacketRecord:
    packet_id: str
    report_id: str
    packet_status: str
    approved_evidence_count: int
    blocked_evidence_count: int
    approved_evidence_ids: List[str]
    blocked_evidence_ids: List[str]
    source_table_status: str
    transcript_table_status: str
    timestamp_table_status: str
    quote_table_status: str
    manual_review_table_status: str
    approval_table_status: str
    release_readiness_status: str
    release_policy_status: str
    audit_trail_status: str
    packet_ready: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    blocker_reasons: List[str]
    packet_notes: str

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
            f"FinalApprovedEvidencePacketRecord.{field_name} must be a "
            "non-empty string"
        )


def _require_nonnegative_int(data: Dict[str, Any], field_name: str) -> int:
    value = data.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(
            f"FinalApprovedEvidencePacketRecord.{field_name} must be a "
            "non-negative integer"
        )
    return value


def _require_string_list(data: Dict[str, Any], field_name: str) -> List[str]:
    value = data.get(field_name)
    if not isinstance(value, list):
        raise ValueError(
            f"FinalApprovedEvidencePacketRecord.{field_name} must be a list"
        )
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"FinalApprovedEvidencePacketRecord.{field_name} must contain "
                "non-empty strings"
            )
    return value


def _require_blocker_reasons(data: Dict[str, Any]) -> List[str]:
    reasons = data.get("blocker_reasons")
    if not isinstance(reasons, list):
        raise ValueError(
            "FinalApprovedEvidencePacketRecord.blocker_reasons must be a list"
        )
    for reason in reasons:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(
                "FinalApprovedEvidencePacketRecord.blocker_reasons must contain "
                "non-empty strings"
            )
    return reasons


def _reject_packet_claims(data: Dict[str, Any]) -> None:
    text = "\n".join(_string_values(data)).lower()
    for claim in FORBIDDEN_PACKET_CLAIMS:
        if claim in text:
            raise ValueError(
                "FinalApprovedEvidencePacketRecord contains prohibited readiness "
                f"claim: {claim}"
            )


def validate_final_approved_packet_record(record: Any) -> None:
    data = _as_dict(record)

    for field_name in (
        "packet_id",
        "report_id",
        "packet_status",
        "source_table_status",
        "transcript_table_status",
        "timestamp_table_status",
        "quote_table_status",
        "manual_review_table_status",
        "approval_table_status",
        "release_readiness_status",
        "release_policy_status",
        "audit_trail_status",
        "packet_notes",
    ):
        _require_nonempty_string(data, field_name)

    if data["packet_status"] not in PACKET_STATUSES:
        raise ValueError(
            "FinalApprovedEvidencePacketRecord.packet_status is unsupported: "
            f"{data['packet_status']}"
        )

    approved_count = _require_nonnegative_int(data, "approved_evidence_count")
    blocked_count = _require_nonnegative_int(data, "blocked_evidence_count")
    approved_ids = _require_string_list(data, "approved_evidence_ids")
    blocked_ids = _require_string_list(data, "blocked_evidence_ids")
    if approved_count != len(approved_ids):
        raise ValueError(
            "FinalApprovedEvidencePacketRecord.approved_evidence_count must match "
            "approved_evidence_ids"
        )
    if blocked_count != len(blocked_ids):
        raise ValueError(
            "FinalApprovedEvidencePacketRecord.blocked_evidence_count must match "
            "blocked_evidence_ids"
        )
    if set(approved_ids) & set(blocked_ids):
        raise ValueError(
            "FinalApprovedEvidencePacketRecord blocked evidence IDs must not "
            "appear in approved_evidence_ids"
        )

    if data.get("public_ready") is not False:
        raise ValueError("FinalApprovedEvidencePacketRecord.public_ready must be false")
    if data.get("institutional_ready") is not False:
        raise ValueError(
            "FinalApprovedEvidencePacketRecord.institutional_ready must be false"
        )
    if data.get("report_ready") is not False:
        raise ValueError("FinalApprovedEvidencePacketRecord.report_ready must be false")
    if not isinstance(data.get("packet_ready"), bool):
        raise ValueError(
            "FinalApprovedEvidencePacketRecord.packet_ready must be a boolean"
        )

    if data.get("packet_ready") is True:
        if approved_count <= 0:
            raise ValueError(
                "FinalApprovedEvidencePacketRecord.packet_ready requires "
                "approved_evidence_count > 0"
            )
        if data["packet_status"] != "approved_packet_candidate":
            raise ValueError(
                "FinalApprovedEvidencePacketRecord.packet_ready requires "
                "packet_status=approved_packet_candidate"
            )

    if data["packet_status"] == "approved_packet_candidate" and approved_count <= 0:
        raise ValueError(
            "FinalApprovedEvidencePacketRecord.approved_packet_candidate requires "
            "approved_evidence_count > 0"
        )
    if data["packet_status"] == "blocked_no_approved_evidence" and approved_count != 0:
        raise ValueError(
            "FinalApprovedEvidencePacketRecord.blocked_no_approved_evidence "
            "requires approved_evidence_count == 0"
        )

    reasons = _require_blocker_reasons(data)
    if data["packet_status"] in BLOCKED_PACKET_STATUSES and not reasons:
        raise ValueError(
            "FinalApprovedEvidencePacketRecord blocked packet statuses require "
            "blocker_reasons"
        )

    _reject_packet_claims(data)


def _load_approval_records(
    input_path: Path = DEFAULT_REAL_EVIDENCE_APPROVAL_RECORDS_OUTPUT,
) -> List[Dict[str, Any]]:
    if not input_path.exists():
        approve_real_evidence_dry_run()

    artifact = json.loads(input_path.read_text(encoding="utf-8"))
    records = artifact.get("records")
    if not isinstance(records, list):
        raise ValueError("Real evidence approval artifact must contain records")

    loaded = [_as_dict(record) for record in records]
    for record in loaded:
        validate_real_evidence_approval_record(record)
    return loaded


def build_final_approved_packet_record_dry_run() -> FinalApprovedEvidencePacketRecord:
    approval_records = _load_approval_records()
    readiness_summary = check_release_readiness_dry_run()
    policy_summary = check_release_policy_dry_run()

    approved_ids = [
        str(record["evidence_id"])
        for record in approval_records
        if record.get("approval_candidate") is True
        and record.get("approval_status") == "approved_evidence_candidate"
    ]
    blocked_ids = [
        str(record["evidence_id"])
        for record in approval_records
        if str(record["evidence_id"]) not in approved_ids
    ]

    if not approved_ids:
        packet_status = "blocked_no_approved_evidence"
        packet_ready = False
        blocker_reasons = list(DRY_RUN_BLOCKER_REASONS)
    elif readiness_summary["release_blocked"] is True:
        packet_status = "blocked_release_not_authorized"
        packet_ready = False
        blocker_reasons = [
            "release readiness remains blocked",
            "public release authorization absent",
            "institutional release authorization absent",
        ]
    else:
        packet_status = "approved_packet_candidate"
        packet_ready = True
        blocker_reasons = []

    record = FinalApprovedEvidencePacketRecord(
        packet_id="FINAL_APPROVED_EVIDENCE_PACKET_V1_DRY_RUN",
        report_id=str(readiness_summary["report_id"]),
        packet_status=packet_status,
        approved_evidence_count=len(approved_ids),
        blocked_evidence_count=len(blocked_ids),
        approved_evidence_ids=approved_ids,
        blocked_evidence_ids=blocked_ids,
        source_table_status="blocked_pending_approval",
        transcript_table_status="blocked_pending_approval",
        timestamp_table_status="blocked_pending_approval",
        quote_table_status="blocked_pending_approval",
        manual_review_table_status="available_but_not_release_approval",
        approval_table_status=(
            "approved_evidence_candidates_available"
            if approved_ids
            else "no_approved_evidence_candidates"
        ),
        release_readiness_status=str(readiness_summary["release_status"]),
        release_policy_status=str(policy_summary["policy_status"]),
        audit_trail_status="dry_run_audit_available",
        packet_ready=packet_ready,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        blocker_reasons=blocker_reasons,
        packet_notes=(
            "Final Approved Evidence Packet v1 dry-run only. The packet remains "
            "blocked until approved evidence candidates exist and release "
            "authorization is complete."
        ),
    )
    validate_final_approved_packet_record(record)
    return record


def write_final_approved_packet_outputs(
    record: FinalApprovedEvidencePacketRecord,
    output_dir: Path = DEFAULT_FINAL_APPROVED_PACKET_DIR,
) -> Dict[str, str]:
    validate_final_approved_packet_record(record)
    output_dir.mkdir(parents=True, exist_ok=True)
    record_path = output_dir / "final_approved_packet_record.json"
    summary_path = output_dir / "final_approved_packet_summary.json"

    summary = {
        "generated_at_utc": utc_now_iso(),
        "mode": "dry-run",
        "packet_id": record.packet_id,
        "report_id": record.report_id,
        "packet_status": record.packet_status,
        "approved_evidence_count": record.approved_evidence_count,
        "blocked_evidence_count": record.blocked_evidence_count,
        "packet_ready": record.packet_ready,
        "public_ready": record.public_ready,
        "institutional_ready": record.institutional_ready,
        "report_ready": record.report_ready,
        "record_output": str(record_path),
        "summary_output": str(summary_path),
    }

    save_json(
        {
            "metadata": {
                "generated_at_utc": utc_now_iso(),
                "mode": "dry-run",
                "packet_ready": record.packet_ready,
                "public_ready": False,
                "institutional_ready": False,
                "report_ready": False,
            },
            "record": record.to_dict(),
        },
        str(record_path),
    )
    save_json(summary, str(summary_path))
    return {
        "record_output": str(record_path),
        "summary_output": str(summary_path),
    }


def generate_final_approved_packet_dry_run(
    output_dir: Path = DEFAULT_FINAL_APPROVED_PACKET_DIR,
) -> Dict[str, Any]:
    record = build_final_approved_packet_record_dry_run()
    outputs = write_final_approved_packet_outputs(record, output_dir)
    return {
        "packet_id": record.packet_id,
        "report_id": record.report_id,
        "packet_status": record.packet_status,
        "approved_evidence_count": record.approved_evidence_count,
        "blocked_evidence_count": record.blocked_evidence_count,
        "packet_ready": record.packet_ready,
        "public_ready": record.public_ready,
        "institutional_ready": record.institutional_ready,
        "report_ready": record.report_ready,
        "record": record,
        **outputs,
    }
