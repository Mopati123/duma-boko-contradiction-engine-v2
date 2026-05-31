#!/usr/bin/env python3
"""
Real Tag Evidence Engine v1.

Verifies an existing release-candidate Git tag as evidence. This lane does not
create tags, push tags, sign release notes, authorize release, or mark
production ready.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict
import hashlib
import json
import subprocess


RELEASE_TAG = "v1.0.0-rc1-governance-runtime"
EXPECTED_TAGGED_COMMIT = "a5052fac67eabc974b23c30040bd50bb914c7626"

DEFAULT_OUTPUT_DIR = Path("outputs/real_tag_evidence")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "real_tag_evidence_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "real_tag_evidence_summary.json"

ALLOWED_STATUSES = {
    "REAL_TAG_EVIDENCE_VERIFIED",
    "BLOCKED_TAG_MISSING_LOCAL",
    "BLOCKED_TAG_COMMIT_MISMATCH",
    "BLOCKED_TAG_MISSING_ORIGIN",
    "BLOCKED_TAG_ORIGIN_MISMATCH",
    "REAL_TAG_EVIDENCE_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "notes_signed_with_real_key",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class RealTagEvidenceRecord:
    real_tag_evidence_id: str
    real_tag_evidence_status: str
    tag_name: str
    local_tag_ref: str
    origin_tag_ref: str
    tagged_commit: str
    expected_tagged_commit: str
    real_tag_evidence_root: str
    tag_exists_locally: bool
    git_tag_created: bool
    tag_pushed_to_origin: bool
    notes_signed_with_real_key: bool
    production_ready: bool
    approved_evidence: int
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_json(payload: Dict[str, Any]) -> str:
    return _sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _tag_ref(tag_name: str) -> str:
    output = _run_git(["show-ref", "--tags", tag_name])
    if not output:
        return ""
    return output.split()[0]


def _tagged_commit(tag_name: str) -> str:
    return _run_git(["rev-parse", f"{tag_name}^{{commit}}"])


def _origin_tag_ref(tag_name: str) -> str:
    output = _run_git(["ls-remote", "--tags", "origin", tag_name])
    if not output:
        return ""
    return output.split()[0]


def _determine_status(
    local_tag_ref: str,
    tagged_commit: str,
    origin_tag_ref: str,
) -> str:
    if not local_tag_ref:
        return "BLOCKED_TAG_MISSING_LOCAL"
    if tagged_commit != EXPECTED_TAGGED_COMMIT:
        return "BLOCKED_TAG_COMMIT_MISMATCH"
    if not origin_tag_ref:
        return "BLOCKED_TAG_MISSING_ORIGIN"
    if origin_tag_ref != local_tag_ref:
        return "BLOCKED_TAG_ORIGIN_MISMATCH"
    return "REAL_TAG_EVIDENCE_VERIFIED"


def validate_record(record: RealTagEvidenceRecord) -> None:
    data = record.to_dict()
    required = {
        "real_tag_evidence_id",
        "real_tag_evidence_status",
        "tag_name",
        "local_tag_ref",
        "origin_tag_ref",
        "tagged_commit",
        "expected_tagged_commit",
        "real_tag_evidence_root",
        "tag_exists_locally",
        "git_tag_created",
        "tag_pushed_to_origin",
        "notes_signed_with_real_key",
        "production_ready",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "notes",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"RealTagEvidenceRecord missing fields: {sorted(missing)}")
    if data["real_tag_evidence_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported real_tag_evidence_status: {data['real_tag_evidence_status']}")

    if data["real_tag_evidence_status"] == "REAL_TAG_EVIDENCE_VERIFIED":
        for key in ("local_tag_ref", "origin_tag_ref", "tagged_commit", "real_tag_evidence_root"):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")
        if data["tag_exists_locally"] is not True:
            raise ValueError("tag_exists_locally must be true for verified tag evidence")
        if data["git_tag_created"] is not True:
            raise ValueError("git_tag_created must be true for verified existing tag evidence")
        if data["tag_pushed_to_origin"] is not True:
            raise ValueError("tag_pushed_to_origin must be true for verified existing tag evidence")

    if data["expected_tagged_commit"] != EXPECTED_TAGGED_COMMIT:
        raise ValueError("expected_tagged_commit changed unexpectedly")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")
    if int(data.get("approved_evidence", 0)) != 0:
        raise ValueError("approved_evidence must remain 0")


def build_real_tag_evidence(tag_name: str = RELEASE_TAG) -> Dict[str, Any]:
    local_tag_ref = _tag_ref(tag_name)
    tagged_commit = _tagged_commit(tag_name)
    origin_tag_ref = _origin_tag_ref(tag_name)
    status = _determine_status(local_tag_ref, tagged_commit, origin_tag_ref)

    tag_exists_locally = bool(local_tag_ref)
    tag_pushed = bool(origin_tag_ref) and origin_tag_ref == local_tag_ref
    root = _hash_json(
        {
            "real_tag_evidence_status": status,
            "tag_name": tag_name,
            "local_tag_ref": local_tag_ref,
            "origin_tag_ref": origin_tag_ref,
            "tagged_commit": tagged_commit,
            "expected_tagged_commit": EXPECTED_TAGGED_COMMIT,
            "tag_exists_locally": tag_exists_locally,
            "git_tag_created": tag_exists_locally,
            "tag_pushed_to_origin": tag_pushed,
            "notes_signed_with_real_key": False,
            "production_ready": False,
        }
    )

    record = RealTagEvidenceRecord(
        real_tag_evidence_id=f"REAL_TAG_EVIDENCE_{root[:16]}",
        real_tag_evidence_status=status,
        tag_name=tag_name,
        local_tag_ref=local_tag_ref,
        origin_tag_ref=origin_tag_ref,
        tagged_commit=tagged_commit,
        expected_tagged_commit=EXPECTED_TAGGED_COMMIT,
        real_tag_evidence_root=root,
        tag_exists_locally=tag_exists_locally,
        git_tag_created=tag_exists_locally,
        tag_pushed_to_origin=tag_pushed,
        notes_signed_with_real_key=False,
        production_ready=False,
        approved_evidence=0,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        notes=(
            "Existing real Git tag evidence only. This engine verified the tag but did not "
            "create or push it, did not sign release notes, and did not authorize production."
        ),
    )
    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"records": [record.to_dict()]}
    summary = {
        "real_tag_evidence_record_count": 1,
        "real_tag_evidence_verified_count": 1 if status == "REAL_TAG_EVIDENCE_VERIFIED" else 0,
        "real_tag_evidence_blocked_count": 0 if status == "REAL_TAG_EVIDENCE_VERIFIED" else 1,
        "real_tag_evidence_status": status,
        "tag_name": tag_name,
        "local_tag_ref": local_tag_ref,
        "origin_tag_ref": origin_tag_ref,
        "tagged_commit": tagged_commit,
        "expected_tagged_commit": EXPECTED_TAGGED_COMMIT,
        "real_tag_evidence_root": root,
        "tag_exists_locally": tag_exists_locally,
        "git_tag_created": tag_exists_locally,
        "tag_pushed_to_origin": tag_pushed,
        "notes_signed_with_real_key": False,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    return {"payload": payload, "summary": summary}
