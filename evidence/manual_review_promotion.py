"""
manual_review_promotion.py - Guarded manual-review promotion gate.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
import json
import shutil

from evidence.real_evidence_inputs import (
    DEFAULT_REAL_EVIDENCE_INPUT_DIR,
    HUMAN_ENTRY_FIELDS,
    validate_real_evidence_input_record,
)


DEFAULT_MANUAL_REVIEW_PROMOTION_OUTPUT_DIR = Path("outputs/manual_review_promotion")
DEFAULT_MANUAL_REVIEW_PROMOTION_STATUS_OUTPUT = (
    DEFAULT_MANUAL_REVIEW_PROMOTION_OUTPUT_DIR / "manual_review_promotion_status.json"
)
DEFAULT_MANUAL_REVIEW_PROMOTION_SUMMARY_OUTPUT = (
    DEFAULT_MANUAL_REVIEW_PROMOTION_OUTPUT_DIR / "manual_review_promotion_summary.json"
)

JOBS_EVIDENCE_ID = "VID_JOBS_001"
HEALTH_EVIDENCE_ID = "VID_HEALTH_001"

CURRENT_REVIEW_STATUS = "entered_pending_review"
APPROVAL_REVIEW_STATUS = "verified_for_approval_review"
PROMOTION_REVIEWER = "manual-review-promotion-v1"

PROMOTION_STATUSES = {
    "promotion_ready",
    "promoted_to_approval_review",
    "blocked_missing_required_fields",
    "blocked_invalid_status",
}

FORBIDDEN_FIELDS = (
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)

TEMPLATE_FIELDS = (
    "evidence_id",
    "case_id",
    "source_url",
    *HUMAN_ENTRY_FIELDS,
    "verification_status",
)


@dataclass
class ManualReviewPromotionRecord:
    evidence_id: str
    case_id: str
    template_path: str
    current_verification_status: str
    proposed_verification_status: str
    promotion_status: str
    missing_required_fields: List[str]
    blocker_reasons: List[str]
    would_write_template: bool
    backup_path: str
    approved_evidence: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    notes: str
    proposed_template: Dict[str, str]

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


def _contains_key(value: Any, target_key: str) -> bool:
    if isinstance(value, dict):
        return target_key in value or any(
            _contains_key(item, target_key) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_key(item, target_key) for item in value)
    return False


def _ordered_template(record: Dict[str, str]) -> Dict[str, str]:
    return {field: str(record.get(field, "")) for field in TEMPLATE_FIELDS}


def load_promotion_templates(
    evidence_id: str = "",
    template_dir: Path = DEFAULT_REAL_EVIDENCE_INPUT_DIR,
) -> List[Tuple[Path, Dict[str, str]]]:
    if evidence_id and evidence_id not in {JOBS_EVIDENCE_ID, HEALTH_EVIDENCE_ID}:
        raise ValueError(f"Unsupported evidence_id for manual review promotion: {evidence_id}")

    paths = [
        template_dir / f"{JOBS_EVIDENCE_ID}.template.json",
        template_dir / f"{HEALTH_EVIDENCE_ID}.template.json",
    ]
    if evidence_id:
        paths = [template_dir / f"{evidence_id}.template.json"]

    templates: List[Tuple[Path, Dict[str, str]]] = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Template must be a JSON object: {path}")
        _reject_forbidden_template_fields(data)
        record = {field: str(data.get(field, "")) for field in TEMPLATE_FIELDS}
        validate_real_evidence_input_record(record)
        templates.append((path, record))
    return templates


def missing_required_fields(template_record: Dict[str, str]) -> List[str]:
    required_fields = ("evidence_id", "case_id", "source_url", *HUMAN_ENTRY_FIELDS)
    return [
        field_name
        for field_name in required_fields
        if not str(template_record.get(field_name, "")).strip()
    ]


def _reject_forbidden_template_fields(data: Dict[str, Any]) -> None:
    for field_name in FORBIDDEN_FIELDS:
        if data.get(field_name) is True:
            raise ValueError(f"Manual review promotion must not set {field_name}=true")
    if data.get("approved_evidence") is True:
        raise ValueError("Manual review promotion must not approve evidence")
    if "verified_for_approval_review" in data:
        raise ValueError(
            "Manual review promotion must not contain verified_for_approval_review "
            "boolean field"
        )


def build_manual_review_promotion_record(
    template_record: Dict[str, str],
    template_path: Path = Path(""),
) -> ManualReviewPromotionRecord:
    _reject_forbidden_template_fields(template_record)
    validate_real_evidence_input_record(template_record)
    evidence_id = str(template_record.get("evidence_id", ""))
    current_status = str(template_record.get("verification_status", ""))
    proposed = _ordered_template(template_record)
    blockers: List[str] = []

    if current_status != CURRENT_REVIEW_STATUS:
        promotion_status = "blocked_invalid_status"
        blockers.append(
            f"verification_status must be {CURRENT_REVIEW_STATUS} before promotion"
        )
    else:
        missing = missing_required_fields(template_record)
        if missing:
            promotion_status = "blocked_missing_required_fields"
            blockers.append("missing required fields: " + ", ".join(missing))
        else:
            promotion_status = "promotion_ready"
            proposed["verification_status"] = APPROVAL_REVIEW_STATUS

    missing = missing_required_fields(template_record)
    if promotion_status == "promotion_ready":
        validate_real_evidence_input_record(proposed)
    else:
        proposed["verification_status"] = current_status

    notes = (
        "Promotion gate inspected existing template fields only; no transcript, "
        "quote, timestamp, approval, or readiness value was created."
    )

    record = ManualReviewPromotionRecord(
        evidence_id=evidence_id,
        case_id=str(template_record.get("case_id", "")),
        template_path=str(template_path),
        current_verification_status=current_status,
        proposed_verification_status=proposed.get("verification_status", ""),
        promotion_status=promotion_status,
        missing_required_fields=missing,
        blocker_reasons=blockers,
        would_write_template=False,
        backup_path="",
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        notes=notes,
        proposed_template=proposed,
    )
    validate_manual_review_promotion_record(record)
    return record


def validate_manual_review_promotion_record(record: Any) -> None:
    data = _as_dict(record)

    for field_name in (
        "evidence_id",
        "case_id",
        "template_path",
        "current_verification_status",
        "proposed_verification_status",
        "promotion_status",
        "notes",
    ):
        value = data.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"ManualReviewPromotionRecord.{field_name} must be a non-empty string"
            )

    if data["promotion_status"] not in PROMOTION_STATUSES:
        raise ValueError(
            "ManualReviewPromotionRecord.promotion_status is unsupported: "
            f"{data['promotion_status']}"
        )

    if data.get("approved_evidence") is not False:
        raise ValueError("ManualReviewPromotionRecord.approved_evidence must be false")
    if data.get("public_ready") is not False:
        raise ValueError("ManualReviewPromotionRecord.public_ready must be false")
    if data.get("institutional_ready") is not False:
        raise ValueError(
            "ManualReviewPromotionRecord.institutional_ready must be false"
        )
    if data.get("report_ready") is not False:
        raise ValueError("ManualReviewPromotionRecord.report_ready must be false")

    missing = data.get("missing_required_fields")
    if not isinstance(missing, list):
        raise ValueError(
            "ManualReviewPromotionRecord.missing_required_fields must be a list"
        )
    blockers = data.get("blocker_reasons")
    if not isinstance(blockers, list):
        raise ValueError("ManualReviewPromotionRecord.blocker_reasons must be a list")

    proposed = data.get("proposed_template")
    if not isinstance(proposed, dict):
        raise ValueError("ManualReviewPromotionRecord.proposed_template must be an object")
    _reject_forbidden_template_fields(proposed)

    if data["promotion_status"] in {
        "blocked_missing_required_fields",
        "blocked_invalid_status",
    }:
        if not blockers:
            raise ValueError("Blocked promotion records require blocker_reasons")
        if data["proposed_verification_status"] != data["current_verification_status"]:
            raise ValueError("Blocked promotion records must not change status")
    else:
        if missing:
            raise ValueError("Promotion-ready records must not have missing fields")
        if data["proposed_verification_status"] != APPROVAL_REVIEW_STATUS:
            raise ValueError(
                "Promotion-ready records must propose verified_for_approval_review"
            )
        validate_real_evidence_input_record(proposed)

    if data["promotion_status"] == "promoted_to_approval_review":
        if data.get("would_write_template") is not True:
            raise ValueError("Promoted records must set would_write_template=true")
    elif data.get("would_write_template") is not False:
        raise ValueError("Non-promoted records must set would_write_template=false")

    forbidden_claim_text = "\n".join(_string_values(data)).lower()
    for claim in (
        "public_ready: true",
        "institutional_ready: true",
        "report_ready: true",
        "approved_evidence=true",
    ):
        if claim in forbidden_claim_text:
            raise ValueError(
                "ManualReviewPromotionRecord contains prohibited claim: " + claim
            )

    if _contains_key(data, "verified_for_approval_review"):
        raise ValueError(
            "ManualReviewPromotionRecord must not contain a "
            "verified_for_approval_review boolean field"
        )

    json.dumps(data)


def _write_template(path: Path, proposed_record: Dict[str, str]) -> str:
    validate_real_evidence_input_record(proposed_record)
    backup_path = path.with_name(f"{path.name}.bak")
    shutil.copy2(path, backup_path)
    path.write_text(
        json.dumps(_ordered_template(proposed_record), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    return str(backup_path)


def summarize_manual_review_promotions(
    records: List[ManualReviewPromotionRecord],
    mode: str,
) -> Dict[str, Any]:
    return {
        "generated_at_utc": utc_now_iso(),
        "mode": mode,
        "selected_template_count": len(records),
        "promotion_ready_count": sum(
            1 for record in records if record.promotion_status == "promotion_ready"
        ),
        "blocked_missing_required_fields_count": sum(
            1
            for record in records
            if record.promotion_status == "blocked_missing_required_fields"
        ),
        "blocked_invalid_status_count": sum(
            1 for record in records if record.promotion_status == "blocked_invalid_status"
        ),
        "promoted_template_count": sum(
            1
            for record in records
            if record.promotion_status == "promoted_to_approval_review"
        ),
        "write_count": sum(
            1
            for record in records
            if record.promotion_status == "promoted_to_approval_review"
        ),
        "backup_count": sum(1 for record in records if record.backup_path),
        "verified_for_approval_review": sum(
            1
            for record in records
            if record.promotion_status == "promoted_to_approval_review"
        ),
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
        "evidence_ids": [record.evidence_id for record in records],
    }


def write_manual_review_promotion_outputs(
    records: List[ManualReviewPromotionRecord],
    mode: str,
    output_dir: Path = DEFAULT_MANUAL_REVIEW_PROMOTION_OUTPUT_DIR,
) -> Dict[str, str]:
    for record in records:
        validate_manual_review_promotion_record(record)

    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / "manual_review_promotion_status.json"
    summary_path = output_dir / "manual_review_promotion_summary.json"

    summary = summarize_manual_review_promotions(records, mode)
    summary["status_output"] = str(status_path)
    summary["summary_output"] = str(summary_path)
    status = {
        "metadata": {
            "generated_at_utc": utc_now_iso(),
            "mode": mode,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
            "report_ready": False,
        },
        "records": [record.to_dict() for record in records],
    }

    status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return {"status_output": str(status_path), "summary_output": str(summary_path)}


def promote_manual_review(
    evidence_id: str = "",
    write: bool = False,
    template_dir: Path = DEFAULT_REAL_EVIDENCE_INPUT_DIR,
    output_dir: Path = DEFAULT_MANUAL_REVIEW_PROMOTION_OUTPUT_DIR,
) -> Dict[str, Any]:
    templates = load_promotion_templates(evidence_id=evidence_id, template_dir=template_dir)
    records: List[ManualReviewPromotionRecord] = []

    for path, template_record in templates:
        record = build_manual_review_promotion_record(template_record, template_path=path)
        if write and record.promotion_status == "promotion_ready":
            backup_path = _write_template(path, record.proposed_template)
            record.promotion_status = "promoted_to_approval_review"
            record.would_write_template = True
            record.backup_path = backup_path
            validate_manual_review_promotion_record(record)
        records.append(record)

    mode = "write" if write else "dry-run"
    outputs = write_manual_review_promotion_outputs(records, mode=mode, output_dir=output_dir)
    summary = summarize_manual_review_promotions(records, mode=mode)
    summary.update(outputs)
    summary["records"] = records
    return summary
