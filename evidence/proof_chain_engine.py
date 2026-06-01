#!/usr/bin/env python3
"""
Proof Chain Engine v2.

Builds deterministic proof chains from contradiction graph edges. The proof
chains are schema/demo records only; they are not approved evidence and do not
mark production, public, or institutional readiness.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import copy
import hashlib
import json


DEFAULT_EDGES = Path("outputs/contradiction_graph_engine/contradiction_edges.json")
DEFAULT_GRAPH_SUMMARY = Path(
    "outputs/contradiction_graph_engine/contradiction_graph_summary.json"
)
DEFAULT_NORMALIZED_CLAIMS = Path("outputs/claim_normalization_engine/normalized_claims.json")
DEFAULT_EXTRACTED_CLAIMS = Path("outputs/claim_extraction_engine/extracted_claims.json")
DEFAULT_LOCALIZED_PACKETS = Path(
    "outputs/evidence_localization_engine/localized_evidence_packets.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/proof_chain_engine")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "proof_chain_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "proof_chain_summary.json"
CHAINS_OUTPUT = DEFAULT_OUTPUT_DIR / "proof_chains.json"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "proof_chain_schema.json"

ENGINE_STATUS = "PROOF_CHAIN_ENGINE_CANDIDATE"
SCHEMA_VERSION = "proof_chain_engine_v2"
PROOF_CHAIN_STATUS = "candidate_sample_proof_chain"

PROOF_STEPS = (
    "evidence_collected",
    "evidence_localized",
    "claim_extracted",
    "claim_normalized",
    "relationship_detected",
    "contradiction_evaluated",
    "proof_chain_assembled",
)

PROOF_CHAIN_FIELDS = (
    "proof_chain_id",
    "case_id",
    "edge_id",
    "relationship_type",
    "contradiction_type",
    "contradiction_found",
    "proof_steps",
    "source_claim",
    "target_claim",
    "source_evidence_anchors",
    "target_evidence_anchors",
    "source_evidence_hashes",
    "target_evidence_hashes",
    "reasoning_summary",
    "confidence_score",
    "severity",
    "chain_valid",
    "proof_chain_root",
    "proof_chain_status",
)

EVIDENCE_ANCHOR_FIELDS = (
    "video_timestamp_start",
    "video_timestamp_end",
    "transcript_start_line",
    "transcript_end_line",
    "screenshot_reference",
    "document_page_start",
    "document_page_end",
    "source_reference",
)


@dataclass
class ProofChain:
    proof_chain_id: str
    case_id: str
    edge_id: str
    relationship_type: str
    contradiction_type: str
    contradiction_found: bool
    proof_steps: List[str]
    source_claim: Dict[str, Any]
    target_claim: Dict[str, Any]
    source_evidence_anchors: Dict[str, Any]
    target_evidence_anchors: Dict[str, Any]
    source_evidence_hashes: List[str]
    target_evidence_hashes: List[str]
    reasoning_summary: str
    confidence_score: float
    severity: str
    chain_valid: bool
    proof_chain_root: str
    proof_chain_status: str

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


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string")


def _closed_flags(data: Dict[str, Any]) -> bool:
    return (
        data.get("production_ready") is False
        and data.get("approved_evidence") == 0
        and data.get("public_ready") is False
        and data.get("institutional_ready") is False
    )


def _has_video_anchor(anchors: Dict[str, Any]) -> bool:
    return bool(anchors.get("video_timestamp_start")) and bool(
        anchors.get("video_timestamp_end")
    )


def _has_transcript_anchor(anchors: Dict[str, Any]) -> bool:
    start = int(anchors.get("transcript_start_line") or 0)
    end = int(anchors.get("transcript_end_line") or 0)
    return start > 0 and end >= start


def _has_screenshot_anchor(anchors: Dict[str, Any]) -> bool:
    return bool(anchors.get("screenshot_reference"))


def _has_document_anchor(anchors: Dict[str, Any]) -> bool:
    start = int(anchors.get("document_page_start") or 0)
    end = int(anchors.get("document_page_end") or 0)
    return start > 0 and end >= start


def _has_forensic_anchor(anchors: Dict[str, Any]) -> bool:
    return any(
        (
            _has_video_anchor(anchors),
            _has_transcript_anchor(anchors),
            _has_screenshot_anchor(anchors),
            _has_document_anchor(anchors),
        )
    )


def _proof_chain_schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "proof_chain_fields": list(PROOF_CHAIN_FIELDS),
        "proof_steps": list(PROOF_STEPS),
        "evidence_anchor_fields": list(EVIDENCE_ANCHOR_FIELDS),
        "proof_chain_status": PROOF_CHAIN_STATUS,
        "root_rules": {
            "proof_chain_root": "sha256 over proof chain excluding proof_chain_root",
            "proof_chain_engine_root": "sha256 over sorted proof chain roots",
        },
        "closed_governance_flags": {
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        },
    }


def validate_proof_chain_schema(schema: Dict[str, Any]) -> None:
    if schema.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("proof_chain_schema schema_version changed unexpectedly")
    if schema.get("proof_chain_fields") != list(PROOF_CHAIN_FIELDS):
        raise ValueError("proof_chain_schema fields changed unexpectedly")
    if schema.get("proof_steps") != list(PROOF_STEPS):
        raise ValueError("proof_chain_schema proof_steps changed unexpectedly")


def _validate_upstream(
    edges_payload: Dict[str, Any],
    graph_summary: Dict[str, Any],
    normalized_payload: Dict[str, Any],
    extracted_payload: Dict[str, Any],
    localized_payload: Dict[str, Any],
) -> str:
    if not edges_payload:
        return "BLOCKED_MISSING_CONTRADICTION_EDGES"
    if not graph_summary:
        return "BLOCKED_MISSING_CONTRADICTION_GRAPH_SUMMARY"
    if not normalized_payload:
        return "BLOCKED_MISSING_NORMALIZED_CLAIMS"
    if not extracted_payload:
        return "BLOCKED_MISSING_EXTRACTED_CLAIMS"
    if not localized_payload:
        return "BLOCKED_MISSING_LOCALIZED_PACKETS"
    if graph_summary.get("contradiction_graph_status") != "CONTRADICTION_GRAPH_ENGINE_CANDIDATE":
        return "BLOCKED_INVALID_CONTRADICTION_GRAPH_SUMMARY"
    if graph_summary.get("edge_count") != 3 or graph_summary.get("valid_edge_count") != 3:
        return "BLOCKED_INVALID_CONTRADICTION_GRAPH_SUMMARY"
    if graph_summary.get("invalid_edge_count") != 0:
        return "BLOCKED_INVALID_CONTRADICTION_GRAPH_SUMMARY"
    if graph_summary.get("contradiction_count") != 1:
        return "BLOCKED_INVALID_CONTRADICTION_GRAPH_SUMMARY"
    if graph_summary.get("contradiction_graph_ready") is not True:
        return "BLOCKED_INVALID_CONTRADICTION_GRAPH_SUMMARY"
    if not _is_nonzero_hash(graph_summary.get("contradiction_graph_root")):
        return "BLOCKED_INVALID_CONTRADICTION_GRAPH_SUMMARY"
    if not _closed_flags(graph_summary):
        return "BLOCKED_INVALID_CONTRADICTION_GRAPH_SUMMARY"

    edges = edges_payload.get("edges")
    normalized_claims = normalized_payload.get("normalized_claims")
    extracted_claims = extracted_payload.get("claims")
    localized_packets = localized_payload.get("localized_packets")
    if not isinstance(edges, list) or len(edges) != 3:
        return "BLOCKED_INVALID_CONTRADICTION_EDGES"
    if not isinstance(normalized_claims, list) or len(normalized_claims) != 3:
        return "BLOCKED_INVALID_NORMALIZED_CLAIMS"
    if not isinstance(extracted_claims, list) or len(extracted_claims) != 3:
        return "BLOCKED_INVALID_EXTRACTED_CLAIMS"
    if not isinstance(localized_packets, list) or len(localized_packets) != 3:
        return "BLOCKED_INVALID_LOCALIZED_PACKETS"
    try:
        normalized_ids = {claim["normalized_claim_id"] for claim in normalized_claims}
        extracted_ids = {claim["claim_id"] for claim in extracted_claims}
        packet_ids = {packet["packet_id"] for packet in localized_packets}
        for edge in edges:
            for field_name in (
                "edge_id",
                "source_claim_id",
                "target_claim_id",
                "source_normalized_claim_id",
                "target_normalized_claim_id",
                "edge_root",
            ):
                _require_nonempty_string(edge, field_name, "ContradictionEdge")
            if edge["source_normalized_claim_id"] not in normalized_ids:
                return "BLOCKED_INVALID_CONTRADICTION_EDGES"
            if edge["target_normalized_claim_id"] not in normalized_ids:
                return "BLOCKED_INVALID_CONTRADICTION_EDGES"
            if edge["source_claim_id"] not in extracted_ids:
                return "BLOCKED_INVALID_CONTRADICTION_EDGES"
            if edge["target_claim_id"] not in extracted_ids:
                return "BLOCKED_INVALID_CONTRADICTION_EDGES"
            if not _is_nonzero_hash(edge["edge_root"]):
                return "BLOCKED_INVALID_CONTRADICTION_EDGES"
            source_anchors = edge.get("evidence_anchors", {}).get("source")
            target_anchors = edge.get("evidence_anchors", {}).get("target")
            if not _has_forensic_anchor(source_anchors or {}):
                return "BLOCKED_INVALID_CONTRADICTION_EDGES"
            if not _has_forensic_anchor(target_anchors or {}):
                return "BLOCKED_INVALID_CONTRADICTION_EDGES"
        for claim in normalized_claims:
            if claim.get("packet_id") not in packet_ids:
                return "BLOCKED_INVALID_NORMALIZED_CLAIMS"
    except (KeyError, TypeError, ValueError):
        return "BLOCKED_INVALID_PROOF_CHAIN_INPUTS"
    return ENGINE_STATUS


def _proof_chain_root_material(chain: ProofChain) -> Dict[str, Any]:
    data = chain.to_dict()
    data.pop("proof_chain_root", None)
    return data


def _assign_proof_chain_root(chain: ProofChain) -> ProofChain:
    chain.proof_chain_root = _hash_json(_proof_chain_root_material(chain))
    return chain


def _claim_reference(
    normalized_claim: Dict[str, Any],
    extracted_claim: Dict[str, Any],
    localized_packet: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "claim_id": extracted_claim["claim_id"],
        "normalized_claim_id": normalized_claim["normalized_claim_id"],
        "case_id": normalized_claim["case_id"],
        "packet_id": normalized_claim["packet_id"],
        "claim_type": extracted_claim["claim_type"],
        "normalized_domain": normalized_claim["normalized_domain"],
        "normalized_action": normalized_claim["normalized_action"],
        "comparison_key": normalized_claim["comparison_key"],
        "claim_root": extracted_claim["claim_root"],
        "normalized_claim_root": normalized_claim["normalized_claim_root"],
        "packet_root": localized_packet["packet_root"],
        "localized_packet_root": localized_packet["localized_packet_root"],
    }


def _proof_chain_for_edge(
    edge: Dict[str, Any],
    normalized_by_id: Dict[str, Dict[str, Any]],
    extracted_by_id: Dict[str, Dict[str, Any]],
    localized_by_packet_id: Dict[str, Dict[str, Any]],
) -> ProofChain:
    source_normalized = normalized_by_id[edge["source_normalized_claim_id"]]
    target_normalized = normalized_by_id[edge["target_normalized_claim_id"]]
    source_extracted = extracted_by_id[edge["source_claim_id"]]
    target_extracted = extracted_by_id[edge["target_claim_id"]]
    source_packet = localized_by_packet_id[source_normalized["packet_id"]]
    target_packet = localized_by_packet_id[target_normalized["packet_id"]]
    chain = ProofChain(
        proof_chain_id=edge["edge_id"].replace("EDGE_", "PROOF_CHAIN_"),
        case_id=edge["case_id"],
        edge_id=edge["edge_id"],
        relationship_type=edge["relationship_type"],
        contradiction_type=edge["contradiction_type"],
        contradiction_found=edge["contradiction_found"],
        proof_steps=list(PROOF_STEPS),
        source_claim=_claim_reference(source_normalized, source_extracted, source_packet),
        target_claim=_claim_reference(target_normalized, target_extracted, target_packet),
        source_evidence_anchors=copy.deepcopy(edge["evidence_anchors"]["source"]),
        target_evidence_anchors=copy.deepcopy(edge["evidence_anchors"]["target"]),
        source_evidence_hashes=list(edge["evidence_hashes"]["source"]),
        target_evidence_hashes=list(edge["evidence_hashes"]["target"]),
        reasoning_summary=edge["reasoning_summary"],
        confidence_score=edge["confidence_score"],
        severity=edge["severity"],
        chain_valid=True,
        proof_chain_root="",
        proof_chain_status=PROOF_CHAIN_STATUS,
    )
    return _assign_proof_chain_root(chain)


def validate_proof_chain(chain: Any, edges_by_id: Dict[str, Dict[str, Any]]) -> None:
    data = chain.to_dict() if hasattr(chain, "to_dict") else chain
    if not isinstance(data, dict):
        raise ValueError("ProofChain must be a dictionary-like value")
    if tuple(data.keys()) != PROOF_CHAIN_FIELDS:
        raise ValueError("ProofChain fields changed unexpectedly")
    for field_name in (
        "proof_chain_id",
        "case_id",
        "edge_id",
        "relationship_type",
        "contradiction_type",
        "reasoning_summary",
        "severity",
        "proof_chain_root",
        "proof_chain_status",
    ):
        _require_nonempty_string(data, field_name, "ProofChain")
    if data["proof_chain_status"] != PROOF_CHAIN_STATUS:
        raise ValueError("ProofChain.proof_chain_status changed unexpectedly")
    if data["proof_steps"] != list(PROOF_STEPS):
        raise ValueError("ProofChain.proof_steps changed unexpectedly")
    if data["chain_valid"] is not True:
        raise ValueError("ProofChain.chain_valid must be true")
    edge = edges_by_id.get(data["edge_id"])
    if not edge:
        raise ValueError("ProofChain references unknown edge")
    for field_name in ("relationship_type", "contradiction_type", "contradiction_found"):
        if data[field_name] != edge[field_name]:
            raise ValueError(f"ProofChain.{field_name} must match edge")
    if data["source_evidence_anchors"] != edge["evidence_anchors"]["source"]:
        raise ValueError("ProofChain source anchors must match edge")
    if data["target_evidence_anchors"] != edge["evidence_anchors"]["target"]:
        raise ValueError("ProofChain target anchors must match edge")
    if data["source_evidence_hashes"] != edge["evidence_hashes"]["source"]:
        raise ValueError("ProofChain source hashes must match edge")
    if data["target_evidence_hashes"] != edge["evidence_hashes"]["target"]:
        raise ValueError("ProofChain target hashes must match edge")
    if not _has_forensic_anchor(data["source_evidence_anchors"]):
        raise ValueError("ProofChain source anchors are invalid")
    if not _has_forensic_anchor(data["target_evidence_anchors"]):
        raise ValueError("ProofChain target anchors are invalid")
    if not _is_nonzero_hash(data["source_claim"]["claim_root"]):
        raise ValueError("ProofChain source claim root must be non-zero")
    if not _is_nonzero_hash(data["target_claim"]["claim_root"]):
        raise ValueError("ProofChain target claim root must be non-zero")
    if not _is_nonzero_hash(data["proof_chain_root"]):
        raise ValueError("ProofChain.proof_chain_root must be non-zero")
    expected_root = _hash_json(
        {key: value for key, value in data.items() if key != "proof_chain_root"}
    )
    if data["proof_chain_root"] != expected_root:
        raise ValueError(f"ProofChain.proof_chain_root mismatch for {data['proof_chain_id']}")


def build_proof_chain_engine(
    edges_path: Path = DEFAULT_EDGES,
    graph_summary_path: Path = DEFAULT_GRAPH_SUMMARY,
    normalized_claims_path: Path = DEFAULT_NORMALIZED_CLAIMS,
    extracted_claims_path: Path = DEFAULT_EXTRACTED_CLAIMS,
    localized_packets_path: Path = DEFAULT_LOCALIZED_PACKETS,
) -> Dict[str, Any]:
    edges_payload = _load_json(edges_path)
    graph_summary = _load_json(graph_summary_path)
    normalized_payload = _load_json(normalized_claims_path)
    extracted_payload = _load_json(extracted_claims_path)
    localized_payload = _load_json(localized_packets_path)
    status = _validate_upstream(
        edges_payload,
        graph_summary,
        normalized_payload,
        extracted_payload,
        localized_payload,
    )
    schema = _proof_chain_schema()
    validate_proof_chain_schema(schema)

    edges = edges_payload.get("edges", []) if status == ENGINE_STATUS else []
    normalized_claims = normalized_payload.get("normalized_claims", []) if status == ENGINE_STATUS else []
    extracted_claims = extracted_payload.get("claims", []) if status == ENGINE_STATUS else []
    localized_packets = localized_payload.get("localized_packets", []) if status == ENGINE_STATUS else []
    normalized_by_id = {claim["normalized_claim_id"]: claim for claim in normalized_claims}
    extracted_by_id = {claim["claim_id"]: claim for claim in extracted_claims}
    localized_by_packet_id = {packet["packet_id"]: packet for packet in localized_packets}
    chains = [
        _proof_chain_for_edge(edge, normalized_by_id, extracted_by_id, localized_by_packet_id)
        for edge in edges
    ]
    chain_dicts = [chain.to_dict() for chain in chains]

    edges_by_id = {edge["edge_id"]: edge for edge in edges}
    valid_count = 0
    proof_roots: List[str] = []
    for chain in chain_dicts:
        validate_proof_chain(chain, edges_by_id)
        valid_count += 1
        proof_roots.append(chain["proof_chain_root"])

    contradiction_count = sum(1 for chain in chain_dicts if chain["contradiction_found"])
    support_count = sum(1 for chain in chain_dicts if chain["relationship_type"] == "SUPPORTS")
    related_count = sum(1 for chain in chain_dicts if chain["relationship_type"] == "RELATED")
    engine_root = _hash_json({"proof_chain_roots": sorted(proof_roots)})
    schema_hash = _hash_json(schema)
    ready = status == ENGINE_STATUS and valid_count == 3
    payload = {
        "records": [
            {
                "proof_chain_status": status,
                "input_edge_count": len(edges),
                "proof_chain_count": len(chain_dicts),
                "valid_proof_chain_count": valid_count,
                "contradiction_proof_count": contradiction_count,
                "support_proof_count": support_count,
                "related_proof_count": related_count,
                "proof_chain_schema_hash": schema_hash,
                "proof_chain_engine_root": engine_root,
                "production_ready": False,
                "approved_evidence": 0,
                "public_ready": False,
                "institutional_ready": False,
            }
        ]
    }
    summary = {
        "proof_chain_status": status,
        "input_edge_count": len(edges),
        "proof_chain_count": len(chain_dicts),
        "valid_proof_chain_count": valid_count,
        "contradiction_proof_count": contradiction_count,
        "support_proof_count": support_count,
        "related_proof_count": related_count,
        "proof_chain_schema_ready": True,
        "proof_chain_engine_ready": ready,
        "proof_chain_roots": proof_roots,
        "proof_chain_schema_hash": schema_hash,
        "proof_chain_engine_root": engine_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(STATUS_OUTPUT, payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(CHAINS_OUTPUT, {"proof_chains": chain_dicts})
    _write_json(SCHEMA_OUTPUT, schema)
    return {
        "payload": payload,
        "summary": summary,
        "proof_chains": chain_dicts,
        "schema": schema,
    }
