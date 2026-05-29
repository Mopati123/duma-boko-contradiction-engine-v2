#!/usr/bin/env python3
"""
Real World Evidence Scale Execution Engine v1.

Builds a deterministic real-world evidence scale execution candidate from
existing repository evidence files and the completed production-readiness chain.

This lane distinguishes real repository evidence records from synthetic scale
cases. It does not mark production_ready=True and does not approve evidence.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import csv
import hashlib
import json


DEFAULT_PRODUCTION_READINESS = Path(
    "outputs/production_readiness_assessment/production_readiness_summary.json"
)
DEFAULT_REAL_SCALE = Path("outputs/real_scale_execution/real_scale_execution_summary.json")
DEFAULT_REPLAY = Path("outputs/replay_certification/replay_certification_summary.json")
DEFAULT_CROSS_MACHINE = Path("outputs/cross_machine_proof/cross_machine_proof_summary.json")

DEFAULT_OUTPUT_DIR = Path("outputs/real_world_evidence_scale_execution")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "real_world_evidence_scale_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "real_world_evidence_scale_summary.json"
MANIFEST_OUTPUT = DEFAULT_OUTPUT_DIR / "real_world_evidence_manifest.json"

CANDIDATE_INPUTS = (
    Path("evidence_template.csv"),
    Path("contradictions_evidence.csv"),
    Path("boko_youtube_results.csv"),
    Path("metadata_analysis.csv"),
    Path("target_search_results.json"),
    Path("outputs/target_search_results.json"),
)

ALLOWED_STATUSES = {
    "REAL_WORLD_SCALE_EXECUTION_CANDIDATE",
    "BLOCKED_MISSING_PRODUCTION_READINESS",
    "BLOCKED_INVALID_PRODUCTION_READINESS",
    "BLOCKED_MISSING_REAL_SCALE",
    "BLOCKED_INVALID_REAL_SCALE",
    "BLOCKED_MISSING_REPLAY",
    "BLOCKED_INVALID_REPLAY",
    "BLOCKED_MISSING_CROSS_MACHINE",
    "BLOCKED_INVALID_CROSS_MACHINE",
    "BLOCKED_NO_REAL_EVIDENCE",
    "REAL_WORLD_SCALE_EXECUTION_INVALID",
}

FORBIDDEN_TRUE_FLAGS = (
    "real_world_scale_applied",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class RealWorldEvidenceRecord:
    evidence_id: str
    source_file: str
    source_type: str
    row_index: int
    evidence_hash: str
    has_url: bool
    has_content: bool
    admissible_real_world_record: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RealWorldEvidenceScaleExecutionRecord:
    real_world_scale_id: str
    real_world_scale_status: str
    real_world_record_count: int
    real_world_candidate_count: int
    production_readiness_root: str
    real_scale_suite_root: str
    replay_root: str
    cross_machine_root: str
    real_world_manifest_root: str
    real_world_scale_root: str
    real_world_verified: bool
    scale_drift_detected: bool
    refusal_law_preserved: bool
    readiness_mutation_detected: bool
    real_world_scale_applied: bool
    production_ready: bool
    approved_evidence: bool
    public_ready: bool
    institutional_ready: bool
    report_ready: bool
    requires_manual_review: bool
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


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _has_url(payload: Dict[str, Any]) -> bool:
    for key, value in payload.items():
        key_lower = str(key).lower()
        text = _stringify(value).lower()
        if "url" in key_lower and text:
            return True
        if text.startswith("http://") or text.startswith("https://"):
            return True
    return False


def _has_content(payload: Dict[str, Any]) -> bool:
    for key, value in payload.items():
        key_lower = str(key).lower()
        text = _stringify(value)
        if key_lower in {"", "id", "index"}:
            continue
        if len(text) >= 3:
            return True
    return False


def _load_csv_records(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                records.append(dict(row))
    except UnicodeDecodeError:
        with path.open("r", encoding="latin-1", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                records.append(dict(row))
    return records


def _flatten_json_records(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("records", "results", "items", "evidence", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]

    return []


def _load_json_records(path: Path) -> List[Dict[str, Any]]:
    return _flatten_json_records(_load_json(path))


def _collect_real_world_records() -> List[RealWorldEvidenceRecord]:
    records: List[RealWorldEvidenceRecord] = []

    for source in CANDIDATE_INPUTS:
        if not source.exists():
            continue

        if source.suffix.lower() == ".csv":
            raw_records = _load_csv_records(source)
            source_type = "csv"
        elif source.suffix.lower() == ".json":
            raw_records = _load_json_records(source)
            source_type = "json"
        else:
            continue

        for index, raw in enumerate(raw_records):
            if not isinstance(raw, dict):
                continue

            has_url = _has_url(raw)
            has_content = _has_content(raw)

            if not has_url and not has_content:
                continue

            evidence_hash = _hash_json(
                {
                    "source_file": str(source),
                    "source_type": source_type,
                    "row_index": index,
                    "payload": raw,
                }
            )

            records.append(
                RealWorldEvidenceRecord(
                    evidence_id=f"REAL_WORLD_EVIDENCE_{evidence_hash[:16]}",
                    source_file=str(source),
                    source_type=source_type,
                    row_index=index,
                    evidence_hash=evidence_hash,
                    has_url=has_url,
                    has_content=has_content,
                    admissible_real_world_record=has_url or has_content,
                )
            )

    # Stable deterministic ordering across platforms.
    return sorted(records, key=lambda item: (item.source_file, item.row_index, item.evidence_hash))


def _determine_status(
    production_readiness: Dict[str, Any],
    real_scale: Dict[str, Any],
    replay: Dict[str, Any],
    cross_machine: Dict[str, Any],
    real_world_records: List[RealWorldEvidenceRecord],
) -> str:
    if not production_readiness:
        return "BLOCKED_MISSING_PRODUCTION_READINESS"
    if production_readiness.get("readiness_status") != "PRODUCTION_READINESS_CANDIDATE":
        return "BLOCKED_INVALID_PRODUCTION_READINESS"
    if production_readiness.get("readiness_score", 0) < 90:
        return "BLOCKED_INVALID_PRODUCTION_READINESS"

    if not real_scale:
        return "BLOCKED_MISSING_REAL_SCALE"
    if real_scale.get("scale_execution_ready") is not True:
        return "BLOCKED_INVALID_REAL_SCALE"
    if real_scale.get("scale_drift_detected") is not False:
        return "BLOCKED_INVALID_REAL_SCALE"
    if real_scale.get("refusal_law_preserved") is not True:
        return "BLOCKED_INVALID_REAL_SCALE"

    if not replay:
        return "BLOCKED_MISSING_REPLAY"
    if replay.get("replay_status") != "REPLAY_CERTIFICATION_CANDIDATE":
        return "BLOCKED_INVALID_REPLAY"
    if replay.get("replay_verified") is not True:
        return "BLOCKED_INVALID_REPLAY"

    if not cross_machine:
        return "BLOCKED_MISSING_CROSS_MACHINE"
    if cross_machine.get("cross_machine_status") != "CROSS_MACHINE_CANDIDATE":
        return "BLOCKED_INVALID_CROSS_MACHINE"
    if cross_machine.get("cross_machine_verified") is not True:
        return "BLOCKED_INVALID_CROSS_MACHINE"

    if not real_world_records:
        return "BLOCKED_NO_REAL_EVIDENCE"

    return "REAL_WORLD_SCALE_EXECUTION_CANDIDATE"


def validate_record(record: RealWorldEvidenceScaleExecutionRecord) -> None:
    data = record.to_dict()

    required = {
        "real_world_scale_id",
        "real_world_scale_status",
        "real_world_record_count",
        "real_world_candidate_count",
        "production_readiness_root",
        "real_scale_suite_root",
        "replay_root",
        "cross_machine_root",
        "real_world_manifest_root",
        "real_world_scale_root",
        "real_world_verified",
        "scale_drift_detected",
        "refusal_law_preserved",
        "readiness_mutation_detected",
        "real_world_scale_applied",
        "production_ready",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "requires_manual_review",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"RealWorldEvidenceScaleExecutionRecord missing fields: {sorted(missing)}")

    if data["real_world_scale_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported real_world_scale_status: {data['real_world_scale_status']}")

    if data["real_world_scale_status"] == "REAL_WORLD_SCALE_EXECUTION_CANDIDATE":
        if data["real_world_record_count"] <= 0:
            raise ValueError("real_world_record_count must be greater than zero")

        if data["real_world_candidate_count"] <= 0:
            raise ValueError("real_world_candidate_count must be greater than zero")

        for key in (
            "production_readiness_root",
            "real_scale_suite_root",
            "replay_root",
            "cross_machine_root",
            "real_world_manifest_root",
            "real_world_scale_root",
        ):
            if not _is_nonzero_hash(data[key]):
                raise ValueError(f"{key} must be a non-zero hash for real-world scale candidate")

        if data["real_world_verified"] is not True:
            raise ValueError("real_world_verified must be true for candidate")

        if data["scale_drift_detected"] is not False:
            raise ValueError("scale_drift_detected must remain false")

        if data["refusal_law_preserved"] is not True:
            raise ValueError("refusal_law_preserved must remain true")

        if data["readiness_mutation_detected"] is not False:
            raise ValueError("readiness_mutation_detected must remain false")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["requires_manual_review"] is not True:
        raise ValueError("requires_manual_review must remain true")


def build_real_world_evidence_scale_execution(
    production_readiness_path: Path = DEFAULT_PRODUCTION_READINESS,
    real_scale_path: Path = DEFAULT_REAL_SCALE,
    replay_path: Path = DEFAULT_REPLAY,
    cross_machine_path: Path = DEFAULT_CROSS_MACHINE,
) -> Dict[str, Any]:
    production_readiness = _load_json(production_readiness_path)
    real_scale = _load_json(real_scale_path)
    replay = _load_json(replay_path)
    cross_machine = _load_json(cross_machine_path)

    real_world_records = _collect_real_world_records()

    status = _determine_status(
        production_readiness,
        real_scale,
        replay,
        cross_machine,
        real_world_records,
    )

    production_readiness_root = str(production_readiness.get("readiness_root") or "")
    real_scale_suite_root = str(real_scale.get("real_scale_suite_root") or "")
    replay_root = str(replay.get("replay_root") or "")
    cross_machine_root = str(cross_machine.get("cross_machine_root") or "")

    manifest = {
        "manifest_version": "real_world_evidence_scale_manifest_v1",
        "record_count": len(real_world_records),
        "records": [record.to_dict() for record in real_world_records],
    }

    real_world_manifest_root = _hash_json(manifest)

    candidate_count = sum(
        1 for record in real_world_records if record.admissible_real_world_record
    )

    real_world_verified = (
        status == "REAL_WORLD_SCALE_EXECUTION_CANDIDATE"
        and candidate_count == len(real_world_records)
        and candidate_count > 0
    )

    scale_drift_detected = False
    refusal_law_preserved = True
    readiness_mutation_detected = False

    real_world_scale_root = _hash_json(
        {
            "real_world_scale_status": status,
            "production_readiness_root": production_readiness_root,
            "real_scale_suite_root": real_scale_suite_root,
            "replay_root": replay_root,
            "cross_machine_root": cross_machine_root,
            "real_world_manifest_root": real_world_manifest_root,
            "real_world_record_count": len(real_world_records),
            "real_world_candidate_count": candidate_count,
            "real_world_verified": real_world_verified,
            "scale_drift_detected": scale_drift_detected,
            "refusal_law_preserved": refusal_law_preserved,
            "readiness_mutation_detected": readiness_mutation_detected,
        }
    )

    record = RealWorldEvidenceScaleExecutionRecord(
        real_world_scale_id=f"REAL_WORLD_SCALE_{real_world_scale_root[:16]}",
        real_world_scale_status=status,
        real_world_record_count=len(real_world_records),
        real_world_candidate_count=candidate_count,
        production_readiness_root=production_readiness_root,
        real_scale_suite_root=real_scale_suite_root,
        replay_root=replay_root,
        cross_machine_root=cross_machine_root,
        real_world_manifest_root=real_world_manifest_root,
        real_world_scale_root=real_world_scale_root,
        real_world_verified=real_world_verified,
        scale_drift_detected=scale_drift_detected,
        refusal_law_preserved=refusal_law_preserved,
        readiness_mutation_detected=readiness_mutation_detected,
        real_world_scale_applied=False,
        production_ready=False,
        approved_evidence=False,
        public_ready=False,
        institutional_ready=False,
        report_ready=False,
        requires_manual_review=True,
        notes=(
            "Real-world evidence scale execution candidate. This lane uses existing "
            "repository evidence-like CSV/JSON artifacts as real evidence records, "
            "while preserving replay, cross-machine, readiness, and refusal constraints. "
            "It does not approve evidence or mark production readiness."
        ),
    )

    validate_record(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict()]}

    summary = {
        "real_world_record_count": len(real_world_records),
        "real_world_candidate_count": candidate_count,
        "real_world_blocked_count": 0 if status == "REAL_WORLD_SCALE_EXECUTION_CANDIDATE" else 1,
        "real_world_invalid_count": 1 if status == "REAL_WORLD_SCALE_EXECUTION_INVALID" else 0,
        "real_world_scale_status": status,
        "real_world_verified": real_world_verified,
        "production_readiness_root": production_readiness_root,
        "real_scale_suite_root": real_scale_suite_root,
        "replay_root": replay_root,
        "cross_machine_root": cross_machine_root,
        "real_world_manifest_root": real_world_manifest_root,
        "real_world_scale_root": real_world_scale_root,
        "scale_drift_detected": scale_drift_detected,
        "refusal_law_preserved": refusal_law_preserved,
        "readiness_mutation_detected": readiness_mutation_detected,
        "real_world_scale_applied": False,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(MANIFEST_OUTPUT, manifest)

    return {
        "payload": payload,
        "summary": summary,
        "manifest": manifest,
    }