#!/usr/bin/env python3
"""
External Signing Evidence Template Engine v1.

Creates a deterministic template for future external signing evidence. This lane
does not sign release notes, use private keys, accept placeholders as evidence,
authorize release, or mark production ready.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict
import hashlib
import json


DEFAULT_REAL_TAG_EVIDENCE = Path("outputs/real_tag_evidence/real_tag_evidence_summary.json")
DEFAULT_RELEASE_TAG = Path("outputs/release_tag_and_signed_notes/release_tag_summary.json")

DEFAULT_OUTPUT_DIR = Path("outputs/external_signing_evidence_template")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "external_signing_evidence_template_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "external_signing_evidence_template_summary.json"
TEMPLATE_OUTPUT = DEFAULT_OUTPUT_DIR / "external_signing_evidence_template.json"

PLACEHOLDER = "PENDING_EXTERNAL_SIGNING"

ALLOWED_STATUSES = {
    "EXTERNAL_SIGNING_TEMPLATE_CANDIDATE",
    "BLOCKED_MISSING_REAL_TAG_EVIDENCE",
    "BLOCKED_INVALID_REAL_TAG_EVIDENCE",
    "BLOCKED_MISSING_RELEASE_TAG",
    "BLOCKED_INVALID_RELEASE_TAG",
    "EXTERNAL_SIGNING_TEMPLATE_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "external_signature_present",
    "notes_signed_with_real_key",
    "release_authorized",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class ExternalSigningEvidenceTemplateRecord:
    external_signing_template_id: str
    external_signing_template_status: str
    release_tag: str
    release_candidate_root: str
    real_tag_evidence_root: str
    signing_template_hash: str
    external_signing_template_root: str
    external_signature_present: bool
    notes_signed_with_real_key: bool
    release_authorized: bool
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


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _as_count(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return 0


def _closed_release_flags(payload: Dict[str, Any]) -> bool:
    return (
        payload.get("production_ready") is False
        and payload.get("public_ready") is False
        and payload.get("institutional_ready") is False
        and payload.get("report_ready") is False
        and _as_count(payload.get("approved_evidence")) == 0
    )


def _determine_status(real_tag: Dict[str, Any], release_tag: Dict[str, Any]) -> str:
    if not real_tag:
        return "BLOCKED_MISSING_REAL_TAG_EVIDENCE"
    if real_tag.get("real_tag_evidence_status") != "REAL_TAG_EVIDENCE_VERIFIED":
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if real_tag.get("tag_exists_locally") is not True:
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if real_tag.get("git_tag_created") is not True:
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if real_tag.get("tag_pushed_to_origin") is not True:
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if real_tag.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if not _closed_release_flags(real_tag):
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"
    if not _is_nonzero_hash(real_tag.get("real_tag_evidence_root")):
        return "BLOCKED_INVALID_REAL_TAG_EVIDENCE"

    if not release_tag:
        return "BLOCKED_MISSING_RELEASE_TAG"
    if release_tag.get("release_status") != "RELEASE_TAG_AND_SIGNED_NOTES_CANDIDATE":
        return "BLOCKED_INVALID_RELEASE_TAG"
    if release_tag.get("release_candidate_ready") is not True:
        return "BLOCKED_INVALID_RELEASE_TAG"
    if release_tag.get("notes_signed_with_real_key") is not False:
        return "BLOCKED_INVALID_RELEASE_TAG"
    if not _closed_release_flags(release_tag):
        return "BLOCKED_INVALID_RELEASE_TAG"
    if not _is_nonzero_hash(release_tag.get("release_candidate_root")):
        return "BLOCKED_INVALID_RELEASE_TAG"

    return "EXTERNAL_SIGNING_TEMPLATE_CANDIDATE"


def _signing_template(release_tag: str, release_candidate_root: str) -> Dict[str, Any]:
    return {
        "external_signing_template_version": "external_signing_evidence_template_v1",
        "template_only": True,
        "placeholder_values_are_not_signature": True,
        "external_signature_present": False,
        "notes_signed_with_real_key": False,
        "production_ready": False,
        "required_fields": {
            "signer_name": PLACEHOLDER,
            "signer_role": PLACEHOLDER,
            "signature_timestamp_utc": PLACEHOLDER,
            "signed_release_tag": release_tag,
            "signed_release_candidate_root": release_candidate_root,
            "external_signature_reference": PLACEHOLDER,
            "signature_artifact_hash": PLACEHOLDER,
            "signature_storage_location": PLACEHOLDER,
        },
        "validation_requirements": {
            "signer_name_non_placeholder": True,
            "signer_role_non_placeholder": True,
            "signature_timestamp_utc_non_placeholder": True,
            "signed_release_tag_matches_candidate": True,
            "signed_release_candidate_root_matches_candidate": True,
            "external_signature_reference_non_placeholder": True,
            "signature_artifact_hash_non_placeholder_sha256": True,
            "signature_storage_location_non_placeholder": True,
            "private_key_material_absent": True,
        },
    }


def validate_record(record: ExternalSigningEvidenceTemplateRecord) -> None:
    data = record.to_dict()
    required = {
        "external_signing_template_id",
        "external_signing_template_status",
        "release_tag",
        "release_candidate_root",
        "real_tag_evidence_root",
        "signing_template_hash",
        "external_signing_template_root",
        "external_signature_present",
        "notes_signed_with_real_key",
        "release_authorized",
        "production_ready",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "notes",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"ExternalSigningEvidenceTemplateRecord missing fields: {sorted(missing)}")
    if data["external_signing_template_status"] not in ALLOWED_STATUSES:
        raise ValueError(
            "Unsupported external_signing_template_status: "
            f"{data['external_signing_template_status']}"
        )
    if data["external_signing_template_status"] == "EXTERNAL_SIGNING_TEMPLATE_CANDIDATE":
        for key in (
            "release_candidate_root",
            "real_tag_evidence_root",
            "signing_template_hash",
            "external_signing_template_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash")
    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")
    if int(data.get("approved_evidence", 0)) != 0:
        raise ValueError("approved_evidence must remain 0")


def build_external_signing_evidence_template(
    real_tag_path: Path = DEFAULT_REAL_TAG_EVIDENCE,
    release_tag_path: Path = DEFAULT_RELEASE_TAG,
) -> Dict[str, Any]:
    real_tag = _load_json(real_tag_path)
    release_tag_summary = _load_json(release_tag_path)
    status = _determine_status(real_tag, release_tag_summary)

    release_tag = str(release_tag_summary.get("release_tag") or real_tag.get("tag_name") or "")
    release_candidate_root = str(release_tag_summary.get("release_candidate_root") or "")
    real_tag_root = str(real_tag.get("real_tag_evidence_root") or "")
    template = _signing_template(release_tag, release_candidate_root)
    template_hash = _hash_json(template)
    root = _hash_json(
        {
            "external_signing_template_status": status,
            "release_tag": release_tag,
            "release_candidate_root": release_candidate_root,
            "real_tag_evidence_root": real_tag_root,
            "signing_template_hash": template_hash,
            "external_signature_present": False,
            "notes_signed_with_real_key": False,
            "production_ready": False,
        }
    )

    record = ExternalSigningEvidenceTemplateRecord(
        external_signing_template_id=f"EXTERNAL_SIGNING_TEMPLATE_{root[:16]}",
        external_signing_template_status=status,
        release_tag=release_tag,
        release_candidate_root=release_candidate_root,
        real_tag_evidence_root=real_tag_root,
        signing_template_hash=template_hash,
        external_signing_template_root=root,
        external_signature_present=False,
        notes_signed_with_real_key=False,
        release_authorized=False,
        production_ready=False,
        approved_evidence=0,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        notes=(
            "External signing evidence template only. No real signature or private key "
            "was used, and placeholders are not signing evidence."
        ),
    )
    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"records": [record.to_dict()]}
    summary = {
        "external_signing_template_record_count": 1,
        "external_signing_template_candidate_count": (
            1 if status == "EXTERNAL_SIGNING_TEMPLATE_CANDIDATE" else 0
        ),
        "external_signing_template_blocked_count": (
            0 if status == "EXTERNAL_SIGNING_TEMPLATE_CANDIDATE" else 1
        ),
        "external_signing_template_status": status,
        "release_tag": release_tag,
        "release_candidate_root": release_candidate_root,
        "real_tag_evidence_root": real_tag_root,
        "signing_template_hash": template_hash,
        "external_signing_template_root": root,
        "external_signature_present": False,
        "notes_signed_with_real_key": False,
        "release_authorized": False,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(TEMPLATE_OUTPUT, template)
    return {"payload": payload, "summary": summary, "template": template}
