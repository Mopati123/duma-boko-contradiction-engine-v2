#!/usr/bin/env python3
"""
Manual AFTER Snapshot To Evidence Packets v2.

Converts validated manual AFTER source snapshots into flat manual-review
evidence packets. This lane uses only validated snapshot records and does not
fetch URLs, invent text, modify the source pack, create claims, create
contradictions, run graph/adjudication logic, create proof chains, create final
reports, mark production readiness, or approve evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json


DEFAULT_VALIDATED_SNAPSHOTS = Path(
    "outputs/manual_after_source_snapshot_intake/validated_manual_after_snapshots.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/manual_after_snapshot_to_evidence_packets")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_after_snapshot_packet_summary.json"
PACKETS_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_after_snapshot_evidence_packets.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_after_snapshot_packet_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_after_snapshot_packet_report.md"

SCHEMA_VERSION = "manual_after_snapshot_to_evidence_packets_v2"
UPSTREAM_SCHEMA_VERSION = "manual_after_source_snapshot_intake_v2"

DRY_RUN_STATUS = "MANUAL_AFTER_SNAPSHOT_PACKET_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "MANUAL_AFTER_SNAPSHOT_PACKET_CANDIDATE"
PARTIAL_STATUS = "MANUAL_AFTER_SNAPSHOT_PACKET_PARTIAL"
REFUSED_STATUS = "MANUAL_AFTER_SNAPSHOT_PACKET_REFUSED"

VALIDATED_SNAPSHOT_STATUS = "VALIDATED_MANUAL_AFTER_SOURCE_SNAPSHOT"
TIME_DIRECTION = "AFTER"
SOURCE_TYPE = "MANUAL_AFTER_SOURCE_SNAPSHOT"
UNSPECIFIED = "UNSPECIFIED"

VALIDATED_SNAPSHOT_FIELDS = (
    "snapshot_id",
    "linked_after_candidate_id",
    "url",
    "title",
    "publisher",
    "published_date",
    "snapshot_text",
    "verification_notes",
    "manual_review_required",
    "after_stability_target_id",
    "linked_before_claim_id",
    "target_theme",
    "target_evidence_type",
    "preferred_source_family",
    "validation_status",
    "linked_after_candidate_record_hash",
    "snapshot_text_hash",
    "metadata_hash",
    "snapshot_root",
)
PACKET_FIELDS = (
    "manual_after_snapshot_packet_id",
    "snapshot_id",
    "linked_after_candidate_id",
    "after_stability_target_id",
    "linked_before_claim_id",
    "target_theme",
    "target_evidence_type",
    "preferred_source_family",
    "time_direction",
    "source_type",
    "url",
    "title",
    "publisher",
    "published_date",
    "verification_notes",
    "evidence_text",
    "snapshot_text_hash",
    "metadata_hash",
    "snapshot_root",
    "manual_review_required",
    "packet_hash",
    "packet_root",
)
REFUSAL_FIELDS = (
    "refusal_id",
    "snapshot_id",
    "linked_after_candidate_id",
    "url",
    "refusal_code",
    "refusal_reason",
    "manual_review_required",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "refusal_root",
)
REFUSAL_CODES = (
    "REFUSED_MALFORMED_VALIDATED_SNAPSHOT",
    "REFUSED_UNSUPPORTED_VALIDATION_STATUS",
    "REFUSED_EMPTY_SNAPSHOT_TEXT",
    "REFUSED_SNAPSHOT_TEXT_HASH_MISMATCH",
    "REFUSED_SNAPSHOT_METADATA_HASH_MISMATCH",
    "REFUSED_SNAPSHOT_ROOT_MISMATCH",
    "REFUSED_DUPLICATE_SNAPSHOT_ID",
    "REFUSED_PACKET_HASH_MISMATCH",
    "REFUSED_PACKET_ROOT_MISMATCH",
)


class ManualAfterSnapshotPacketRefusal(ValueError):
    def __init__(self, code: str, reason: str):
        super().__init__(reason)
        self.code = code
        self.reason = reason


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_json(payload: Any) -> str:
    return _sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def _closed_flags(data: Dict[str, Any]) -> bool:
    return (
        data.get("production_ready") is False
        and data.get("approved_evidence") == 0
        and data.get("public_ready") is False
        and data.get("institutional_ready") is False
    )


def _schema_payload() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "upstream_schema_version": UPSTREAM_SCHEMA_VERSION,
        "manual_after_snapshot_to_evidence_packets_only": True,
        "modes": ["dry-run", "from-snapshots"],
        "validated_snapshot_status": VALIDATED_SNAPSHOT_STATUS,
        "time_direction": TIME_DIRECTION,
        "source_type": SOURCE_TYPE,
        "validated_snapshot_fields": list(VALIDATED_SNAPSHOT_FIELDS),
        "packet_fields": list(PACKET_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "packetization_rule": (
            "Each valid manual AFTER source snapshot becomes exactly one flat "
            "manual-review evidence packet."
        ),
        "root_rules": {
            "snapshot_text_hash": "preserved from validated manual AFTER snapshot",
            "metadata_hash": "preserved from validated manual AFTER snapshot",
            "snapshot_root": "preserved from validated manual AFTER snapshot",
            "packet_hash": "sha256 over packet excluding packet_hash and packet_root",
            "packet_root": "sha256 over packet excluding packet_root",
            "refusal_root": "sha256 over refusal excluding refusal_root",
        },
        "guardrails": {
            "urls_fetched": 0,
            "text_invented": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "proof_chains_created": 0,
            "final_reports_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
        },
    }


def _snapshot_metadata_material(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: snapshot[field]
        for field in VALIDATED_SNAPSHOT_FIELDS
        if field not in ("metadata_hash", "snapshot_root")
    }


def _snapshot_root_material(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: snapshot[field]
        for field in VALIDATED_SNAPSHOT_FIELDS
        if field != "snapshot_root"
    }


def _packet_hash_material(packet: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: packet[field]
        for field in PACKET_FIELDS
        if field not in ("packet_hash", "packet_root")
    }


def _packet_root_material(packet: Dict[str, Any]) -> Dict[str, Any]:
    return {field: packet[field] for field in PACKET_FIELDS if field != "packet_root"}


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    return {field: refusal[field] for field in REFUSAL_FIELDS if field != "refusal_root"}


def _require_nonempty_string(data: Dict[str, Any], field_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ManualAfterSnapshotPacketRefusal(
            "REFUSED_MALFORMED_VALIDATED_SNAPSHOT",
            f"{field_name} must be a non-empty string.",
        )


def _load_validated_snapshots(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    if not isinstance(payload, dict) or not payload:
        raise ValueError("validated_manual_after_snapshots.json is missing.")
    if payload.get("schema_version") != UPSTREAM_SCHEMA_VERSION:
        raise ValueError("validated_manual_after_snapshots schema_version is unsupported.")
    snapshots = payload.get("validated_manual_after_snapshots")
    if not isinstance(snapshots, list):
        raise ValueError("validated_manual_after_snapshots must contain a list.")
    return snapshots


def _validate_snapshot(snapshot: Dict[str, Any]) -> None:
    if not isinstance(snapshot, dict) or set(snapshot.keys()) != set(VALIDATED_SNAPSHOT_FIELDS):
        raise ManualAfterSnapshotPacketRefusal(
            "REFUSED_MALFORMED_VALIDATED_SNAPSHOT",
            "Validated manual AFTER snapshot fields do not match upstream schema.",
        )
    for field_name in VALIDATED_SNAPSHOT_FIELDS:
        if field_name == "manual_review_required":
            continue
        _require_nonempty_string(snapshot, field_name)
    if snapshot["manual_review_required"] is not True:
        raise ManualAfterSnapshotPacketRefusal(
            "REFUSED_MALFORMED_VALIDATED_SNAPSHOT",
            "Validated manual AFTER snapshot manual_review_required must remain true.",
        )
    if snapshot["validation_status"] != VALIDATED_SNAPSHOT_STATUS:
        raise ManualAfterSnapshotPacketRefusal(
            "REFUSED_UNSUPPORTED_VALIDATION_STATUS",
            f"Unsupported validation_status: {snapshot['validation_status']}.",
        )
    snapshot_text = snapshot["snapshot_text"]
    if not snapshot_text.strip() or snapshot_text.strip() == UNSPECIFIED:
        raise ManualAfterSnapshotPacketRefusal(
            "REFUSED_EMPTY_SNAPSHOT_TEXT",
            "Validated manual AFTER snapshot snapshot_text must be supplied.",
        )
    if snapshot["snapshot_text_hash"] != _sha256_text(snapshot_text):
        raise ManualAfterSnapshotPacketRefusal(
            "REFUSED_SNAPSHOT_TEXT_HASH_MISMATCH",
            f"snapshot_text_hash mismatch for {snapshot['snapshot_id']}.",
        )
    if snapshot["metadata_hash"] != _hash_json(_snapshot_metadata_material(snapshot)):
        raise ManualAfterSnapshotPacketRefusal(
            "REFUSED_SNAPSHOT_METADATA_HASH_MISMATCH",
            f"metadata_hash mismatch for {snapshot['snapshot_id']}.",
        )
    if snapshot["snapshot_root"] != _hash_json(_snapshot_root_material(snapshot)):
        raise ManualAfterSnapshotPacketRefusal(
            "REFUSED_SNAPSHOT_ROOT_MISMATCH",
            f"snapshot_root mismatch for {snapshot['snapshot_id']}.",
        )


def _validate_snapshot_set(snapshots: List[Dict[str, Any]]) -> None:
    seen_snapshot_ids = set()
    for snapshot in snapshots:
        _validate_snapshot(snapshot)
        snapshot_id = snapshot["snapshot_id"]
        if snapshot_id in seen_snapshot_ids:
            raise ManualAfterSnapshotPacketRefusal(
                "REFUSED_DUPLICATE_SNAPSHOT_ID",
                f"Duplicate snapshot_id: {snapshot_id}.",
            )
        seen_snapshot_ids.add(snapshot_id)


def _make_packet(snapshot: Dict[str, Any], index: int) -> Dict[str, Any]:
    packet = {
        "manual_after_snapshot_packet_id": f"MANUAL_AFTER_SNAPSHOT_EVIDENCE_PACKET_{index:06d}",
        "snapshot_id": snapshot["snapshot_id"],
        "linked_after_candidate_id": snapshot["linked_after_candidate_id"],
        "after_stability_target_id": snapshot["after_stability_target_id"],
        "linked_before_claim_id": snapshot["linked_before_claim_id"],
        "target_theme": snapshot["target_theme"],
        "target_evidence_type": snapshot["target_evidence_type"],
        "preferred_source_family": snapshot["preferred_source_family"],
        "time_direction": TIME_DIRECTION,
        "source_type": SOURCE_TYPE,
        "url": snapshot["url"],
        "title": snapshot["title"],
        "publisher": snapshot["publisher"],
        "published_date": snapshot["published_date"],
        "verification_notes": snapshot["verification_notes"],
        "evidence_text": snapshot["snapshot_text"],
        "snapshot_text_hash": snapshot["snapshot_text_hash"],
        "metadata_hash": snapshot["metadata_hash"],
        "snapshot_root": snapshot["snapshot_root"],
        "manual_review_required": True,
        "packet_hash": "",
        "packet_root": "",
    }
    packet["packet_hash"] = _hash_json(_packet_hash_material(packet))
    packet["packet_root"] = _hash_json(_packet_root_material(packet))
    return packet


def validate_packet(packet: Dict[str, Any]) -> None:
    if set(packet.keys()) != set(PACKET_FIELDS):
        raise ValueError("Manual AFTER snapshot evidence packet fields changed unexpectedly.")
    for field_name in PACKET_FIELDS:
        if field_name == "manual_review_required":
            continue
        value = packet.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"ManualAfterSnapshotEvidencePacket.{field_name} must be non-empty.")
    if packet["time_direction"] != TIME_DIRECTION:
        raise ValueError("Manual AFTER snapshot evidence packet time_direction must be AFTER.")
    if packet["source_type"] != SOURCE_TYPE:
        raise ValueError("Manual AFTER snapshot evidence packet source_type is unsupported.")
    if packet["manual_review_required"] is not True:
        raise ValueError("Manual AFTER snapshot evidence packet manual_review_required must remain true.")
    if packet["packet_hash"] != _hash_json(_packet_hash_material(packet)):
        raise ManualAfterSnapshotPacketRefusal(
            "REFUSED_PACKET_HASH_MISMATCH",
            f"packet_hash mismatch for {packet['manual_after_snapshot_packet_id']}.",
        )
    if packet["packet_root"] != _hash_json(_packet_root_material(packet)):
        raise ManualAfterSnapshotPacketRefusal(
            "REFUSED_PACKET_ROOT_MISMATCH",
            f"packet_root mismatch for {packet['manual_after_snapshot_packet_id']}.",
        )


def _validate_packet_preservation(packet: Dict[str, Any], snapshot: Dict[str, Any]) -> None:
    for field_name in (
        "snapshot_id",
        "linked_after_candidate_id",
        "url",
        "title",
        "publisher",
        "published_date",
        "verification_notes",
        "after_stability_target_id",
        "linked_before_claim_id",
        "target_theme",
        "target_evidence_type",
        "preferred_source_family",
        "snapshot_text_hash",
        "metadata_hash",
        "snapshot_root",
    ):
        if packet[field_name] != snapshot[field_name]:
            raise ValueError(f"Manual AFTER snapshot packet did not preserve {field_name}.")
    if packet["evidence_text"] != snapshot["snapshot_text"]:
        raise ValueError("Manual AFTER snapshot packet did not preserve snapshot_text exactly.")
    if packet["snapshot_text_hash"] != _sha256_text(packet["evidence_text"]):
        raise ValueError("Manual AFTER snapshot packet text hash does not match evidence_text.")


def _snapshot_identity(snapshot: Dict[str, Any], index: int) -> Tuple[str, str, str]:
    return (
        str(snapshot.get("snapshot_id") or f"UNKNOWN_SNAPSHOT_{index:06d}"),
        str(snapshot.get("linked_after_candidate_id") or ""),
        str(snapshot.get("url") or ""),
    )


def _make_refusal(
    snapshot: Dict[str, Any],
    error: ManualAfterSnapshotPacketRefusal,
    index: int,
) -> Dict[str, Any]:
    snapshot_id, linked_after_candidate_id, url = _snapshot_identity(snapshot, index)
    refusal = {
        "refusal_id": f"MANUAL_AFTER_SNAPSHOT_PACKET_REFUSAL_{snapshot_id}",
        "snapshot_id": snapshot_id,
        "linked_after_candidate_id": linked_after_candidate_id,
        "url": url,
        "refusal_code": error.code,
        "refusal_reason": error.reason,
        "manual_review_required": True,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Manual AFTER snapshot packet refusal fields changed unexpectedly.")
    for field_name in ("refusal_id", "snapshot_id", "refusal_code", "refusal_reason", "refusal_root"):
        value = refusal.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"ManualAfterSnapshotPacketRefusal.{field_name} must be non-empty.")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("Manual AFTER snapshot packet refusal manual_review_required must remain true.")
    if not _closed_flags(refusal):
        raise ValueError("Manual AFTER snapshot packet refusal guardrails must remain closed.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}.")


def _packet_or_refusal(
    snapshot: Dict[str, Any],
    index: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    try:
        _validate_snapshot(snapshot)
        packet = _make_packet(snapshot, index)
        validate_packet(packet)
        _validate_packet_preservation(packet, snapshot)
        return packet, None
    except ManualAfterSnapshotPacketRefusal as exc:
        refusal = _make_refusal(snapshot if isinstance(snapshot, dict) else {}, exc, index)
        validate_refusal(refusal)
        return None, refusal
    except ValueError as exc:
        refusal = _make_refusal(
            snapshot if isinstance(snapshot, dict) else {},
            ManualAfterSnapshotPacketRefusal(
                "REFUSED_MALFORMED_VALIDATED_SNAPSHOT",
                str(exc),
            ),
            index,
        )
        validate_refusal(refusal)
        return None, refusal


def _status_for(mode: str, packet_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if packet_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if packet_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _summary_root_material(summary: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {
        "manual_after_snapshot_packet_root",
        "manual_after_snapshot_packet_report_hash",
    }
    return {key: value for key, value in summary.items() if key not in excluded}


def _build_report(
    status: str,
    mode: str,
    snapshot_count: int,
    packets: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    packet_lines = ["- None"]
    if packets:
        packet_lines = []
        for packet in packets[:20]:
            preview = packet["evidence_text"][:160].replace("\n", " ")
            packet_lines.extend(
                [
                    f"- {packet['manual_after_snapshot_packet_id']}",
                    f"  - Snapshot: {packet['snapshot_id']}",
                    f"  - Candidate: {packet['linked_after_candidate_id']}",
                    f"  - Source: {packet['publisher']} | {packet['title']}",
                    f"  - Preview: {preview}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Snapshot: {refusal['snapshot_id']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Manual AFTER Snapshot To Evidence Packets v2",
            "",
            "This lane packetizes validated manual AFTER source snapshots only. "
            "It does not read refused snapshots, fetch URLs, invent text, modify "
            "the source pack, create claims, create contradictions, create proof "
            "chains, create final reports, mark production readiness, or approve "
            "evidence.",
            "",
            "## Summary",
            f"- manual_after_snapshot_packet_status: {status}",
            f"- mode: {mode}",
            f"- validated_snapshot_count: {snapshot_count}",
            f"- manual_after_snapshot_packet_count: {len(packets)}",
            f"- refusal_count: {len(refusals)}",
            f"- manual_after_snapshot_packet_root: {root}",
            "",
            "## First Manual AFTER Snapshot Evidence Packets",
            *packet_lines,
            "",
            "## Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- URLs Fetched: 0",
            "- Text Invented: 0",
            "- Claims Created: 0",
            "- Contradictions Created: 0",
            "- Proof Chains Created: 0",
            "- Final Reports Created: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "",
        ]
    )


def build_manual_after_snapshot_to_evidence_packets(
    mode: str = "dry-run",
    validated_snapshots_path: Path = DEFAULT_VALIDATED_SNAPSHOTS,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "from-snapshots"):
        raise ValueError("mode must be 'dry-run' or 'from-snapshots'.")

    snapshots = _load_validated_snapshots(validated_snapshots_path)
    if mode == "dry-run":
        _validate_snapshot_set(snapshots)
    schema = _schema_payload()

    packets: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    if mode == "from-snapshots":
        seen_snapshot_ids = set()
        for snapshot in snapshots:
            snapshot_id = str(snapshot.get("snapshot_id") or "")
            if snapshot_id in seen_snapshot_ids:
                refusal = _make_refusal(
                    snapshot if isinstance(snapshot, dict) else {},
                    ManualAfterSnapshotPacketRefusal(
                        "REFUSED_DUPLICATE_SNAPSHOT_ID",
                        f"Duplicate snapshot_id: {snapshot_id}.",
                    ),
                    len(packets) + len(refusals) + 1,
                )
                validate_refusal(refusal)
                refusals.append(refusal)
                continue
            seen_snapshot_ids.add(snapshot_id)
            packet, refusal = _packet_or_refusal(snapshot, len(packets) + 1)
            if packet is not None:
                packets.append(packet)
            if refusal is not None:
                refusals.append(refusal)

    status = _status_for(mode, len(packets), len(refusals))
    summary = {
        "manual_after_snapshot_packet_status": status,
        "mode": mode,
        "validated_snapshot_count": len(snapshots),
        "manual_after_snapshot_packet_count": len(packets),
        "refusal_count": len(refusals),
        "validated_snapshot_ids": [
            str(snapshot.get("snapshot_id") or "") for snapshot in snapshots
        ],
        "packet_ids": [
            packet["manual_after_snapshot_packet_id"] for packet in packets
        ],
        "packet_roots": [packet["packet_root"] for packet in packets],
        "refusal_roots": [refusal["refusal_root"] for refusal in refusals],
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "time_direction_counts": {
            TIME_DIRECTION: sum(1 for packet in packets if packet["time_direction"] == TIME_DIRECTION),
        },
        "source_type_counts": {
            SOURCE_TYPE: sum(1 for packet in packets if packet["source_type"] == SOURCE_TYPE),
        },
        "lineage_preserved": True,
        "snapshot_id_preserved": True,
        "source_metadata_preserved": True,
        "snapshot_text_hash_preserved": True,
        "metadata_hash_preserved": True,
        "snapshot_root_preserved": True,
        "evidence_text_exact_copy": True,
        "manual_after_snapshot_packet_schema_hash": _hash_json(schema),
        "manual_after_snapshot_packet_report_hash": "",
        "manual_after_snapshot_packet_root": "",
        "urls_fetched": 0,
        "text_invented": 0,
        "claims_created": 0,
        "contradictions_created": 0,
        "proof_chains_created": 0,
        "final_reports_created": 0,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    summary["manual_after_snapshot_packet_root"] = _hash_json(
        _summary_root_material(summary)
    )
    report = _build_report(
        status,
        mode,
        len(snapshots),
        packets,
        refusals,
        summary["manual_after_snapshot_packet_root"],
    )
    summary["manual_after_snapshot_packet_report_hash"] = _sha256_text(report)
    summary["manual_after_snapshot_packet_root"] = _hash_json(
        _summary_root_material(summary)
    )
    report = _build_report(
        status,
        mode,
        len(snapshots),
        packets,
        refusals,
        summary["manual_after_snapshot_packet_root"],
    )

    if mode == "dry-run" and (packets or refusals):
        raise ValueError("Dry-run must validate manual AFTER snapshots only.")
    for counter_name in (
        "urls_fetched",
        "text_invented",
        "claims_created",
        "contradictions_created",
        "proof_chains_created",
        "final_reports_created",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0.")
    if not _closed_flags(summary):
        raise ValueError("Manual AFTER snapshot packet guardrails must remain closed.")

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(
        output_dir / PACKETS_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "manual_after_snapshot_evidence_packets": packets,
        },
    )
    _write_json(
        output_dir / REFUSALS_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "manual_after_snapshot_packet_refusals": refusals,
        },
    )
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    return {
        "summary": summary,
        "manual_after_snapshot_evidence_packets": packets,
        "manual_after_snapshot_packet_refusals": refusals,
        "schema": schema,
        "report": report,
    }


__all__ = ["build_manual_after_snapshot_to_evidence_packets"]
