#!/usr/bin/env python3
"""
Evidence Packet Engine v2.

Builds deterministic sample evidence packets for the Duma Boko Contradiction
Engine v2 integrated packet format. The samples are schema/demo packets only;
they are not approved evidence and they do not mark production, public, or
institutional readiness.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json


DEFAULT_OUTPUT_DIR = Path("outputs/evidence_packet_engine")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "evidence_packet_engine_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "evidence_packet_engine_summary.json"
PACKETS_OUTPUT = DEFAULT_OUTPUT_DIR / "evidence_packets.json"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "evidence_packet_schema.json"

SCHEMA_VERSION = "evidence_packet_engine_v2"
ENGINE_STATUS = "EVIDENCE_PACKET_ENGINE_CANDIDATE"
PACKET_STATUS = "candidate_sample_packet"
EVIDENCE_VERIFICATION_STATUS = "sample_unverified"

TOP_LEVEL_PACKET_FIELDS = (
    "packet_id",
    "case_id",
    "source_details",
    "source_ownership",
    "speaker",
    "original_promise",
    "current_position",
    "evidence_collection",
    "governance_metadata",
    "packet_root",
    "packet_status",
)

CANONICAL_SECTIONS = (
    "source_details",
    "source_ownership",
    "speaker",
    "original_promise",
    "current_position",
    "evidence_collection",
    "governance_metadata",
)

EVIDENCE_ITEM_REQUIRED_FIELDS = (
    "evidence_id",
    "evidence_type",
    "source_reference",
    "verification_status",
    "hash_sha256",
)

SAMPLE_PACKET_THEMES = (
    "employment_promise",
    "policy_statement",
    "implementation_status",
)


@dataclass
class SourceDetails:
    source_type: str
    source_title: str
    source_date: str
    source_platform: str
    source_url: str
    source_reference_id: str
    source_theme: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SourceOwnership:
    ownership_type: str
    owner_name: str
    correlation_level: str
    verification_status: str
    ownership_notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Speaker:
    speaker_name: str
    speaker_role: str
    political_party: str
    authority_context: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OriginalPromise:
    promise_text: str
    promise_summary: str
    promise_category: str
    promise_date: str
    promise_source_reference: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CurrentPosition:
    position_text: str
    position_summary: str
    position_category: str
    position_date: str
    position_source_reference: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceItem:
    evidence_id: str
    evidence_type: str
    source_reference: str
    verification_status: str
    hash_sha256: str
    evidence_notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceCollection:
    evidence_items: List[EvidenceItem]
    evidence_count: int
    collection_status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_items": [item.to_dict() for item in self.evidence_items],
            "evidence_count": self.evidence_count,
            "collection_status": self.collection_status,
        }


@dataclass
class GovernanceMetadata:
    schema_version: str
    packet_type: str
    deterministic_json: bool
    sha256_roots: bool
    production_ready: bool
    approved_evidence: int
    public_ready: bool
    institutional_ready: bool
    no_generated_outputs_committed: bool
    governance_notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidencePacket:
    packet_id: str
    case_id: str
    source_details: SourceDetails
    source_ownership: SourceOwnership
    speaker: Speaker
    original_promise: OriginalPromise
    current_position: CurrentPosition
    evidence_collection: EvidenceCollection
    governance_metadata: GovernanceMetadata
    packet_root: str
    packet_status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "case_id": self.case_id,
            "source_details": self.source_details.to_dict(),
            "source_ownership": self.source_ownership.to_dict(),
            "speaker": self.speaker.to_dict(),
            "original_promise": self.original_promise.to_dict(),
            "current_position": self.current_position.to_dict(),
            "evidence_collection": self.evidence_collection.to_dict(),
            "governance_metadata": self.governance_metadata.to_dict(),
            "packet_root": self.packet_root,
            "packet_status": self.packet_status,
        }


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_json(payload: Dict[str, Any]) -> str:
    return _sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string")


def _closed_governance_flags(data: Dict[str, Any]) -> bool:
    return (
        data.get("production_ready") is False
        and data.get("approved_evidence") == 0
        and data.get("public_ready") is False
        and data.get("institutional_ready") is False
    )


def _evidence_item_material(
    evidence_id: str,
    evidence_type: str,
    source_reference: str,
    verification_status: str,
    evidence_notes: str,
) -> Dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "evidence_type": evidence_type,
        "source_reference": source_reference,
        "verification_status": verification_status,
        "evidence_notes": evidence_notes,
    }


def _make_evidence_item(
    evidence_id: str,
    evidence_type: str,
    source_reference: str,
    evidence_notes: str,
) -> EvidenceItem:
    material = _evidence_item_material(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        source_reference=source_reference,
        verification_status=EVIDENCE_VERIFICATION_STATUS,
        evidence_notes=evidence_notes,
    )
    return EvidenceItem(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        source_reference=source_reference,
        verification_status=EVIDENCE_VERIFICATION_STATUS,
        hash_sha256=_hash_json(material),
        evidence_notes=evidence_notes,
    )


def _packet_root_material(packet: EvidencePacket) -> Dict[str, Any]:
    data = packet.to_dict()
    data.pop("packet_root", None)
    return data


def _assign_packet_root(packet: EvidencePacket) -> EvidencePacket:
    packet.packet_root = _hash_json(_packet_root_material(packet))
    return packet


def _governance_metadata() -> GovernanceMetadata:
    return GovernanceMetadata(
        schema_version=SCHEMA_VERSION,
        packet_type="sample_schema_packet",
        deterministic_json=True,
        sha256_roots=True,
        production_ready=False,
        approved_evidence=0,
        public_ready=False,
        institutional_ready=False,
        no_generated_outputs_committed=True,
        governance_notes=(
            "Deterministic sample packet for schema validation only. This is not "
            "approved evidence and does not authorize production readiness."
        ),
    )


def _sample_packets() -> List[EvidencePacket]:
    packets = [
        EvidencePacket(
            packet_id="PACKET_SAMPLE_001",
            case_id="CASE_SAMPLE_001",
            source_details=SourceDetails(
                source_type="campaign_rally",
                source_title="Sample employment promise source",
                source_date="2024-01-01",
                source_platform="sample_platform",
                source_url="sample://employment-promise",
                source_reference_id="SRC_SAMPLE_EMPLOYMENT_001",
                source_theme="employment_promise",
            ),
            source_ownership=SourceOwnership(
                ownership_type="sample_reference",
                owner_name="Schema Sample Corpus",
                correlation_level="sample",
                verification_status="sample_unverified",
                ownership_notes="Synthetic sample ownership metadata for packet schema validation.",
            ),
            speaker=Speaker(
                speaker_name="Duma Boko",
                speaker_role="sample political leader",
                political_party="sample party",
                authority_context="sample_context",
            ),
            original_promise=OriginalPromise(
                promise_text="Sample promise to improve employment outcomes.",
                promise_summary="Employment promise sample for packet schema validation.",
                promise_category="employment",
                promise_date="2024-01-01",
                promise_source_reference="SRC_SAMPLE_EMPLOYMENT_001",
            ),
            current_position=CurrentPosition(
                position_text="",
                position_summary="No real current position asserted in this sample packet.",
                position_category="not_assessed",
                position_date="2024-01-02",
                position_source_reference="SRC_SAMPLE_EMPLOYMENT_001",
            ),
            evidence_collection=EvidenceCollection(
                evidence_items=[
                    _make_evidence_item(
                        evidence_id="EVID_SAMPLE_EMPLOYMENT_001",
                        evidence_type="sample_text_reference",
                        source_reference="SRC_SAMPLE_EMPLOYMENT_001",
                        evidence_notes="Sample evidence item for employment promise theme.",
                    )
                ],
                evidence_count=1,
                collection_status="sample_unverified",
            ),
            governance_metadata=_governance_metadata(),
            packet_root="",
            packet_status=PACKET_STATUS,
        ),
        EvidencePacket(
            packet_id="PACKET_SAMPLE_002",
            case_id="CASE_SAMPLE_002",
            source_details=SourceDetails(
                source_type="official_statement",
                source_title="Sample policy statement source",
                source_date="2024-02-01",
                source_platform="sample_platform",
                source_url="sample://policy-statement",
                source_reference_id="SRC_SAMPLE_POLICY_002",
                source_theme="policy_statement",
            ),
            source_ownership=SourceOwnership(
                ownership_type="sample_reference",
                owner_name="Schema Sample Corpus",
                correlation_level="sample",
                verification_status="sample_unverified",
                ownership_notes="Synthetic sample ownership metadata for packet schema validation.",
            ),
            speaker=Speaker(
                speaker_name="Duma Boko",
                speaker_role="sample political leader",
                political_party="sample party",
                authority_context="sample_context",
            ),
            original_promise=OriginalPromise(
                promise_text="",
                promise_summary="No real original promise asserted in this sample packet.",
                promise_category="not_assessed",
                promise_date="2024-02-01",
                promise_source_reference="SRC_SAMPLE_POLICY_002",
            ),
            current_position=CurrentPosition(
                position_text="Sample government policy statement position.",
                position_summary="Policy statement sample for packet schema validation.",
                position_category="policy_statement",
                position_date="2024-02-02",
                position_source_reference="SRC_SAMPLE_POLICY_002",
            ),
            evidence_collection=EvidenceCollection(
                evidence_items=[
                    _make_evidence_item(
                        evidence_id="EVID_SAMPLE_POLICY_002",
                        evidence_type="sample_statement_reference",
                        source_reference="SRC_SAMPLE_POLICY_002",
                        evidence_notes="Sample evidence item for policy statement theme.",
                    )
                ],
                evidence_count=1,
                collection_status="sample_unverified",
            ),
            governance_metadata=_governance_metadata(),
            packet_root="",
            packet_status=PACKET_STATUS,
        ),
        EvidencePacket(
            packet_id="PACKET_SAMPLE_003",
            case_id="CASE_SAMPLE_003",
            source_details=SourceDetails(
                source_type="implementation_report",
                source_title="Sample implementation status source",
                source_date="2024-03-01",
                source_platform="sample_platform",
                source_url="sample://implementation-status",
                source_reference_id="SRC_SAMPLE_IMPLEMENTATION_003",
                source_theme="implementation_status",
            ),
            source_ownership=SourceOwnership(
                ownership_type="sample_reference",
                owner_name="Schema Sample Corpus",
                correlation_level="sample",
                verification_status="sample_unverified",
                ownership_notes="Synthetic sample ownership metadata for packet schema validation.",
            ),
            speaker=Speaker(
                speaker_name="Duma Boko",
                speaker_role="sample political leader",
                political_party="sample party",
                authority_context="sample_context",
            ),
            original_promise=OriginalPromise(
                promise_text="Sample implementation commitment under review.",
                promise_summary="Implementation status sample with a promise and current position.",
                promise_category="implementation",
                promise_date="2024-03-01",
                promise_source_reference="SRC_SAMPLE_IMPLEMENTATION_003",
            ),
            current_position=CurrentPosition(
                position_text="Sample implementation status remains under assessment.",
                position_summary="Implementation status sample for packet schema validation.",
                position_category="implementation_status",
                position_date="2024-03-02",
                position_source_reference="SRC_SAMPLE_IMPLEMENTATION_003",
            ),
            evidence_collection=EvidenceCollection(
                evidence_items=[
                    _make_evidence_item(
                        evidence_id="EVID_SAMPLE_IMPLEMENTATION_003",
                        evidence_type="sample_status_reference",
                        source_reference="SRC_SAMPLE_IMPLEMENTATION_003",
                        evidence_notes="Sample evidence item for implementation status theme.",
                    )
                ],
                evidence_count=1,
                collection_status="sample_unverified",
            ),
            governance_metadata=_governance_metadata(),
            packet_root="",
            packet_status=PACKET_STATUS,
        ),
    ]
    return [_assign_packet_root(packet) for packet in packets]


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "top_level_packet_fields": list(TOP_LEVEL_PACKET_FIELDS),
        "canonical_sections": list(CANONICAL_SECTIONS),
        "required_evidence_item_fields": list(EVIDENCE_ITEM_REQUIRED_FIELDS),
        "sample_case_ids": ["CASE_SAMPLE_001", "CASE_SAMPLE_002", "CASE_SAMPLE_003"],
        "sample_packet_themes": list(SAMPLE_PACKET_THEMES),
        "root_rules": {
            "evidence_item_hash": "sha256 over item material excluding hash_sha256",
            "packet_root": "sha256 over packet content excluding packet_root",
            "engine_root": "sha256 over sorted packet roots",
        },
        "closed_governance_flags": {
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        },
    }


def validate_evidence_item(value: Any) -> None:
    data = value.to_dict() if hasattr(value, "to_dict") else value
    if not isinstance(data, dict):
        raise ValueError("EvidenceItem must be a dictionary-like value")
    for field_name in EVIDENCE_ITEM_REQUIRED_FIELDS:
        _require_nonempty_string(data, field_name, "EvidenceItem")
    material = _evidence_item_material(
        evidence_id=data["evidence_id"],
        evidence_type=data["evidence_type"],
        source_reference=data["source_reference"],
        verification_status=data["verification_status"],
        evidence_notes=str(data.get("evidence_notes", "")),
    )
    expected_hash = _hash_json(material)
    if data["hash_sha256"] != expected_hash:
        raise ValueError(f"EvidenceItem.hash_sha256 mismatch for {data['evidence_id']}")


def validate_packet(packet: Any) -> None:
    data = packet.to_dict() if hasattr(packet, "to_dict") else packet
    if not isinstance(data, dict):
        raise ValueError("EvidencePacket must be a dictionary-like value")
    if tuple(data.keys()) != TOP_LEVEL_PACKET_FIELDS:
        raise ValueError("EvidencePacket top-level fields changed unexpectedly")
    for field_name in ("packet_id", "case_id", "packet_status"):
        _require_nonempty_string(data, field_name, "EvidencePacket")
    if data["packet_status"] != PACKET_STATUS:
        raise ValueError(f"EvidencePacket.packet_status is unsupported: {data['packet_status']}")
    for section in CANONICAL_SECTIONS:
        if section not in data or not isinstance(data[section], dict):
            raise ValueError(f"EvidencePacket.{section} must be present")

    _require_nonempty_string(data["source_details"], "source_type", "SourceDetails")
    _require_nonempty_string(data["speaker"], "speaker_name", "Speaker")
    promise_text = data["original_promise"].get("promise_text", "")
    position_text = data["current_position"].get("position_text", "")
    if not str(promise_text).strip() and not str(position_text).strip():
        raise ValueError("EvidencePacket requires an original promise or current position")

    collection = data["evidence_collection"]
    items = collection.get("evidence_items")
    if not isinstance(items, list) or not items:
        raise ValueError("EvidenceCollection.evidence_items must be a non-empty list")
    if collection.get("evidence_count") != len(items):
        raise ValueError("EvidenceCollection.evidence_count must match evidence_items length")
    for item in items:
        validate_evidence_item(item)

    governance = data["governance_metadata"]
    if governance.get("deterministic_json") is not True:
        raise ValueError("GovernanceMetadata.deterministic_json must be true")
    if governance.get("sha256_roots") is not True:
        raise ValueError("GovernanceMetadata.sha256_roots must be true")
    if governance.get("no_generated_outputs_committed") is not True:
        raise ValueError("GovernanceMetadata.no_generated_outputs_committed must be true")
    if not _closed_governance_flags(governance):
        raise ValueError("GovernanceMetadata readiness and approval flags must remain closed")

    packet_root = data.get("packet_root")
    if not _is_nonzero_hash(packet_root):
        raise ValueError("EvidencePacket.packet_root must be a non-zero SHA-256 root")
    root_material = dict(data)
    root_material.pop("packet_root", None)
    expected_root = _hash_json(root_material)
    if packet_root != expected_root:
        raise ValueError(f"EvidencePacket.packet_root mismatch for {data['packet_id']}")


def validate_schema(schema: Dict[str, Any]) -> None:
    if schema.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("evidence_packet_schema schema_version changed unexpectedly")
    if schema.get("top_level_packet_fields") != list(TOP_LEVEL_PACKET_FIELDS):
        raise ValueError("evidence_packet_schema top_level_packet_fields changed unexpectedly")
    if schema.get("canonical_sections") != list(CANONICAL_SECTIONS):
        raise ValueError("evidence_packet_schema canonical_sections changed unexpectedly")
    if schema.get("required_evidence_item_fields") != list(EVIDENCE_ITEM_REQUIRED_FIELDS):
        raise ValueError("evidence_packet_schema required_evidence_item_fields changed unexpectedly")


def build_evidence_packet_engine() -> Dict[str, Any]:
    packets = _sample_packets()
    schema = _schema()
    validate_schema(schema)

    valid_packets = 0
    invalid_packets = 0
    packet_dicts: List[Dict[str, Any]] = []
    packet_roots: List[str] = []
    for packet in packets:
        try:
            validate_packet(packet)
            valid_packets += 1
        except ValueError:
            invalid_packets += 1
            raise
        packet_data = packet.to_dict()
        packet_dicts.append(packet_data)
        packet_roots.append(packet_data["packet_root"])

    schema_hash = _hash_json(schema)
    engine_root = _hash_json({"packet_roots": sorted(packet_roots)})
    ready = valid_packets == 3 and invalid_packets == 0
    status = ENGINE_STATUS if ready else "EVIDENCE_PACKET_ENGINE_INVALID"
    payload = {
        "records": [
            {
                "evidence_packet_status": status,
                "packet_count": len(packet_dicts),
                "valid_packet_count": valid_packets,
                "invalid_packet_count": invalid_packets,
                "schema_hash": schema_hash,
                "evidence_packet_engine_root": engine_root,
                "production_ready": False,
                "approved_evidence": 0,
                "public_ready": False,
                "institutional_ready": False,
            }
        ]
    }
    summary = {
        "evidence_packet_status": status,
        "packet_count": len(packet_dicts),
        "valid_packet_count": valid_packets,
        "invalid_packet_count": invalid_packets,
        "schema_ready": True,
        "evidence_packet_engine_ready": ready,
        "schema_hash": schema_hash,
        "packet_roots": packet_roots,
        "evidence_packet_engine_root": engine_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "no_generated_outputs_committed": True,
        "deterministic_json": True,
        "sha256_roots": True,
    }
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(PACKETS_OUTPUT, {"packets": packet_dicts})
    _write_json(SCHEMA_OUTPUT, schema)
    return {
        "payload": payload,
        "summary": summary,
        "packets": packet_dicts,
        "schema": schema,
    }
