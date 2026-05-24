"""
release_policy.py - Formal local-CI override policy records.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from evidence.evidence_schema import save_json


DEFAULT_RELEASE_POLICY_DIR = Path("outputs/release_policy")
DEFAULT_RELEASE_POLICY_RECORD = DEFAULT_RELEASE_POLICY_DIR / "release_policy_record.json"
DEFAULT_RELEASE_POLICY_SUMMARY = DEFAULT_RELEASE_POLICY_DIR / "release_policy_summary.json"

REQUIRED_CONDITIONS = [
    "local CI passed",
    "working tree is clean",
    "branch is pushed",
    "GitHub Actions did not execute repository code",
    "remote job had zero steps",
    "runner_id is 0",
    "runner_name is empty",
    "error is external billing/account lock",
    "no repository/test/interpreter/dependency failure occurred",
]

PROHIBITED_CONDITIONS = [
    "any repository command ran and failed",
    "any test failed",
    "any Python interpreter error occurred",
    "any dependency installation failed",
    "any lint/type/schema gate failed",
    "branch has uncommitted changes",
    "generated artifacts remain uncleaned",
    "evidence is being promoted to public_ready/report_ready without approval",
]

FORBIDDEN_RELEASE_CLAIMS = (
    "public_ready: true",
    "institutional_ready: true",
    "report_ready: true",
    "public-ready evidence",
    "institution-ready evidence",
    "validated public evidence",
    "final forensic report readiness",
    "ready for public release",
    "ready for institutional release",
)


@dataclass
class ReleasePolicyRecord:
    policy_id: str
    policy_status: str
    local_ci_authority: str
    github_actions_status: str
    manual_override_allowed: bool
    required_conditions: List[str]
    prohibited_conditions: List[str]
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    policy_notes: str

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
        raise ValueError(f"ReleasePolicyRecord.{field_name} must be a non-empty string")


def _require_nonempty_string_list(data: Dict[str, Any], field_name: str) -> List[str]:
    value = data.get(field_name)
    if not isinstance(value, list) or not value:
        raise ValueError(f"ReleasePolicyRecord.{field_name} must be a non-empty list")
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"ReleasePolicyRecord.{field_name} must contain non-empty strings"
            )
    return value


def _reject_release_claims(data: Dict[str, Any]) -> None:
    text = "\n".join(_string_values(data)).lower()
    for claim in FORBIDDEN_RELEASE_CLAIMS:
        if claim in text:
            raise ValueError(
                f"ReleasePolicyRecord contains prohibited release claim: {claim}"
            )


def validate_release_policy_record(record: Any) -> None:
    data = _as_dict(record)

    for field_name in (
        "policy_id",
        "policy_status",
        "local_ci_authority",
        "github_actions_status",
        "policy_notes",
    ):
        _require_nonempty_string(data, field_name)

    _require_nonempty_string_list(data, "required_conditions")
    _require_nonempty_string_list(data, "prohibited_conditions")

    if data.get("public_ready") is not False:
        raise ValueError("ReleasePolicyRecord.public_ready must be false")
    if data.get("institutional_ready") is not False:
        raise ValueError("ReleasePolicyRecord.institutional_ready must be false")
    if data.get("report_ready") is not False:
        raise ValueError("ReleasePolicyRecord.report_ready must be false")

    if data.get("manual_override_allowed") is not True:
        raise ValueError(
            "ReleasePolicyRecord.manual_override_allowed must be true for CI replacement only"
        )

    combined = "\n".join(_string_values(data)).lower()
    if "ci validation replacement" not in combined:
        raise ValueError(
            "ReleasePolicyRecord.manual_override_allowed requires CI validation replacement scope"
        )
    if "not evidence/public/institutional release approval" not in combined:
        raise ValueError(
            "ReleasePolicyRecord.manual_override_allowed must not imply release approval"
        )

    _reject_release_claims(data)


def build_release_policy_record_dry_run() -> ReleasePolicyRecord:
    record = ReleasePolicyRecord(
        policy_id="RELEASE_POLICY_V1_DRY_RUN",
        policy_status="active_local_ci_override_policy",
        local_ci_authority="temporary CI validation replacement only",
        github_actions_status="unavailable_due_to_billing_account_lock",
        manual_override_allowed=True,
        required_conditions=list(REQUIRED_CONDITIONS),
        prohibited_conditions=list(PROHIBITED_CONDITIONS),
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        policy_notes=(
            "Manual override is limited to CI validation replacement and is not "
            "evidence/public/institutional release approval. Release readiness "
            "remains blocked until real evidence and reviewer approval are complete."
        ),
    )
    validate_release_policy_record(record)
    return record


def write_release_policy_outputs(
    record: ReleasePolicyRecord,
    output_dir: Path = DEFAULT_RELEASE_POLICY_DIR,
) -> Dict[str, str]:
    validate_release_policy_record(record)
    output_dir.mkdir(parents=True, exist_ok=True)
    record_path = output_dir / "release_policy_record.json"
    summary_path = output_dir / "release_policy_summary.json"

    summary = {
        "generated_at_utc": utc_now_iso(),
        "mode": "dry-run",
        "policy_id": record.policy_id,
        "policy_status": record.policy_status,
        "local_ci_authority": record.local_ci_authority,
        "github_actions_status": record.github_actions_status,
        "manual_override_allowed": record.manual_override_allowed,
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


def check_release_policy_dry_run(
    output_dir: Path = DEFAULT_RELEASE_POLICY_DIR,
) -> Dict[str, Any]:
    record = build_release_policy_record_dry_run()
    outputs = write_release_policy_outputs(record, output_dir)
    return {
        "policy_id": record.policy_id,
        "policy_status": record.policy_status,
        "local_ci_authority": record.local_ci_authority,
        "github_actions_status": record.github_actions_status,
        "manual_override_allowed": record.manual_override_allowed,
        "public_ready": record.public_ready,
        "institutional_ready": record.institutional_ready,
        "report_ready": record.report_ready,
        "record": record,
        **outputs,
    }
