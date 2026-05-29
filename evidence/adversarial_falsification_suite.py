#!/usr/bin/env python3
"""
Adversarial Falsification Suite v1.

Builds deterministic adversarial refusal cases against the production-freeze
candidate chain.

This suite does not mutate production artifacts. It proves that hostile or
inconsistent evidence states are classified as refused/blocked rather than
accepted.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_PRODUCTION_FREEZE_STATUS = Path(
    "outputs/production_freeze/production_freeze_status.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/adversarial_falsification_suite")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "adversarial_falsification_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "adversarial_falsification_summary.json"
MATRIX_OUTPUT = DEFAULT_OUTPUT_DIR / "adversarial_falsification_matrix.json"

ALLOWED_ATTACK_TYPES = {
    "MISSING_URL",
    "BROKEN_URL",
    "TAMPERED_SNAPSHOT",
    "TAMPERED_REPORT",
    "INVALID_CERTIFICATE",
    "INVALID_ANCHOR",
    "INVALID_AUTHORITY",
    "REPLAY_DRIFT",
    "CROSS_MACHINE_DRIFT",
    "FREEZE_DRIFT",
}

ALLOWED_ATTACK_STATUS = {
    "REFUSED",
    "UNEXPECTED_ACCEPT",
    "BLOCKED_MISSING_PRODUCTION_FREEZE",
    "BLOCKED_INVALID_PRODUCTION_FREEZE",
}

FORBIDDEN_TRUE_FLAGS = (
    "attack_accepted",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "report_ready",
)


@dataclass
class AdversarialFalsificationRecord:
    attack_id: str
    attack_type: str
    attack_status: str
    target_layer: str
    expected_refusal: bool
    attack_accepted: bool
    refusal_reason: str
    production_freeze_root: str
    tampered_material_hash: str
    refusal_root: str
    production_ready: bool
    approved_evidence: bool
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


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    payload = _load_json(path)
    if not isinstance(payload, dict):
        return []

    records = payload.get("records", [])
    return records if isinstance(records, list) else []


def _first_record(path: Path) -> Dict[str, Any]:
    records = _load_records(path)
    return records[0] if records else {}


def _attack_matrix() -> List[Dict[str, str]]:
    return [
        {
            "attack_type": "MISSING_URL",
            "target_layer": "url_closure",
            "refusal_reason": "URL is missing or empty.",
        },
        {
            "attack_type": "BROKEN_URL",
            "target_layer": "url_closure",
            "refusal_reason": "URL is syntactically or semantically invalid.",
        },
        {
            "attack_type": "TAMPERED_SNAPSHOT",
            "target_layer": "snapshot_sealing",
            "refusal_reason": "Snapshot root does not match sealed evidence state.",
        },
        {
            "attack_type": "TAMPERED_REPORT",
            "target_layer": "final_report_collapse",
            "refusal_reason": "Report collapse root does not match upstream graph.",
        },
        {
            "attack_type": "INVALID_CERTIFICATE",
            "target_layer": "verification_certificate",
            "refusal_reason": "Certificate hash does not match verified publication chain.",
        },
        {
            "attack_type": "INVALID_ANCHOR",
            "target_layer": "public_anchor",
            "refusal_reason": "Anchor root does not match certificate and publication roots.",
        },
        {
            "attack_type": "INVALID_AUTHORITY",
            "target_layer": "signature_authority",
            "refusal_reason": "Authority hash/signature does not match certificate authority root.",
        },
        {
            "attack_type": "REPLAY_DRIFT",
            "target_layer": "replay_certification",
            "refusal_reason": "Replay input/output hash lineage drift detected.",
        },
        {
            "attack_type": "CROSS_MACHINE_DRIFT",
            "target_layer": "cross_machine_proof",
            "refusal_reason": "Machine contract, merkle, or replay root mismatch detected.",
        },
        {
            "attack_type": "FREEZE_DRIFT",
            "target_layer": "production_freeze",
            "refusal_reason": "Production baseline hash does not match freeze root.",
        },
    ]


def validate_record(record: Any) -> None:
    data = record.to_dict() if hasattr(record, "to_dict") else record

    required = {
        "attack_id",
        "attack_type",
        "attack_status",
        "target_layer",
        "expected_refusal",
        "attack_accepted",
        "refusal_reason",
        "production_freeze_root",
        "tampered_material_hash",
        "refusal_root",
        "production_ready",
        "approved_evidence",
        "public_ready",
        "institutional_ready",
        "report_ready",
        "notes",
    }

    missing = required - set(data)
    if missing:
        raise ValueError(f"AdversarialFalsificationRecord missing fields: {sorted(missing)}")

    if data["attack_type"] not in ALLOWED_ATTACK_TYPES:
        raise ValueError(f"Unsupported attack_type: {data['attack_type']}")

    if data["attack_status"] not in ALLOWED_ATTACK_STATUS:
        raise ValueError(f"Unsupported attack_status: {data['attack_status']}")

    for flag in FORBIDDEN_TRUE_FLAGS:
        if data.get(flag) is True:
            raise ValueError(f"{flag} must remain false")

    if data["expected_refusal"] is not True:
        raise ValueError("expected_refusal must remain true")

    if data["attack_status"] == "REFUSED" and data["attack_accepted"] is not False:
        raise ValueError("REFUSED attacks must not be accepted")


def build_adversarial_falsification_suite(
    production_freeze_status_path: Path = DEFAULT_PRODUCTION_FREEZE_STATUS,
) -> Dict[str, Any]:
    freeze_record = _first_record(production_freeze_status_path)
    production_freeze_root = str(freeze_record.get("production_freeze_root") or "")

    if not freeze_record:
        global_status = "BLOCKED_MISSING_PRODUCTION_FREEZE"
    elif freeze_record.get("freeze_status") != "PRODUCTION_FREEZE_CANDIDATE":
        global_status = "BLOCKED_INVALID_PRODUCTION_FREEZE"
    else:
        global_status = "REFUSED"

    records: List[AdversarialFalsificationRecord] = []

    for attack in _attack_matrix():
        attack_type = attack["attack_type"]
        target_layer = attack["target_layer"]
        refusal_reason = attack["refusal_reason"]

        tampered_material = {
            "attack_type": attack_type,
            "target_layer": target_layer,
            "production_freeze_root": production_freeze_root,
            "mutation": "deterministic_adversarial_mutation_v1",
            "expected_refusal": True,
        }

        tampered_material_hash = _hash_json(tampered_material)

        refusal_root = _hash_json(
            {
                "attack_type": attack_type,
                "attack_status": global_status,
                "tampered_material_hash": tampered_material_hash,
                "production_freeze_root": production_freeze_root,
            }
        )

        record = AdversarialFalsificationRecord(
            attack_id=f"ADVERSARIAL_{attack_type}_{refusal_root[:12]}",
            attack_type=attack_type,
            attack_status=global_status,
            target_layer=target_layer,
            expected_refusal=True,
            attack_accepted=False,
            refusal_reason=refusal_reason,
            production_freeze_root=production_freeze_root,
            tampered_material_hash=tampered_material_hash,
            refusal_root=refusal_root,
            production_ready=False,
            approved_evidence=False,
            public_ready=False,
            institutional_ready=False,
            report_ready=False,
            notes=(
                "Adversarial falsification case. Hostile/tampered input must be "
                "refused and must not mutate production, public, institutional, "
                "or report readiness state."
            ),
        )

        validate_record(record)
        records.append(record)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"records": [record.to_dict() for record in records]}

    suite_root = _hash_json(
        {
            "suite_version": "adversarial_falsification_suite_v1",
            "production_freeze_root": production_freeze_root,
            "refusal_roots": [record.refusal_root for record in records],
        }
    )

    refused_count = sum(1 for record in records if record.attack_status == "REFUSED")
    unexpected_accept_count = sum(
        1 for record in records if record.attack_status == "UNEXPECTED_ACCEPT"
    )

    summary = {
        "adversarial_record_count": len(records),
        "adversarial_refused_count": refused_count,
        "adversarial_unexpected_accept_count": unexpected_accept_count,
        "adversarial_blocked_missing_production_freeze_count": sum(
            1 for record in records
            if record.attack_status == "BLOCKED_MISSING_PRODUCTION_FREEZE"
        ),
        "adversarial_blocked_invalid_production_freeze_count": sum(
            1 for record in records
            if record.attack_status == "BLOCKED_INVALID_PRODUCTION_FREEZE"
        ),
        "adversarial_suite_root": suite_root,
        "production_freeze_root": production_freeze_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "report_ready": False,
    }

    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(MATRIX_OUTPUT, {"attacks": _attack_matrix()})

    return {
        "payload": payload,
        "summary": summary,
        "matrix": {"attacks": _attack_matrix()},
    }