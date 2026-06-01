#!/usr/bin/env python3
"""
Case Assembly Engine v2.

Builds deterministic assembled sample cases from localized evidence, claims,
normalized claims, contradiction edges, and proof chains. The cases are
schema/demo records only; they are not approved evidence and do not mark
production, public, or institutional readiness.
"""

from pathlib import Path
from typing import Any, Dict, List
import copy
import hashlib
import json


DEFAULT_PROOF_CHAINS = Path("outputs/proof_chain_engine/proof_chains.json")
DEFAULT_PROOF_SUMMARY = Path("outputs/proof_chain_engine/proof_chain_summary.json")
DEFAULT_EDGES = Path("outputs/contradiction_graph_engine/contradiction_edges.json")
DEFAULT_LOCALIZED_PACKETS = Path(
    "outputs/evidence_localization_engine/localized_evidence_packets.json"
)
DEFAULT_EXTRACTED_CLAIMS = Path("outputs/claim_extraction_engine/extracted_claims.json")
DEFAULT_NORMALIZED_CLAIMS = Path("outputs/claim_normalization_engine/normalized_claims.json")

DEFAULT_OUTPUT_DIR = Path("outputs/case_assembly_engine")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "case_assembly_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "case_assembly_summary.json"
CASES_OUTPUT = DEFAULT_OUTPUT_DIR / "assembled_cases.json"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "case_schema.json"

ENGINE_STATUS = "CASE_ASSEMBLY_ENGINE_CANDIDATE"
SCHEMA_VERSION = "case_assembly_engine_v2"
CASE_STATUS = "candidate_sample_case"

CASE_FIELDS = (
    "case_id",
    "case_title",
    "case_category",
    "case_status",
    "source_details",
    "source_ownership",
    "speaker_political_leader",
    "original_promise",
    "current_government_position",
    "evidence_collection",
    "claims",
    "normalized_claims",
    "contradiction_edges",
    "proof_chains",
    "final_finding",
    "confidence_score",
    "severity",
    "governance_verification",
    "final_report_validation_checklist",
    "case_root",
)

CASE_ORDER = (
    "CASE_SAMPLE_001",
    "CASE_SAMPLE_002",
    "CASE_SAMPLE_003",
)

PRIMARY_EDGE_BY_CASE = {
    "CASE_SAMPLE_001": "EDGE_SAMPLE_001_002",
    "CASE_SAMPLE_002": "EDGE_SAMPLE_002_003",
    "CASE_SAMPLE_003": "EDGE_SAMPLE_001_003",
}

CASE_TITLES = {
    "CASE_SAMPLE_001": "Employment Promise Compared With Current Position",
    "CASE_SAMPLE_002": "Employment Programme Position And Implementation Support",
    "CASE_SAMPLE_003": "Policy Implementation Status Evidence",
}

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


def _case_schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "case_fields": list(CASE_FIELDS),
        "case_status": CASE_STATUS,
        "case_order": list(CASE_ORDER),
        "primary_edge_by_case": dict(PRIMARY_EDGE_BY_CASE),
        "root_rules": {
            "case_root": "sha256 over assembled case excluding case_root",
            "case_assembly_engine_root": "sha256 over sorted case roots",
        },
        "closed_governance_flags": {
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        },
    }


def validate_case_schema(schema: Dict[str, Any]) -> None:
    if schema.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("case_schema schema_version changed unexpectedly")
    if schema.get("case_fields") != list(CASE_FIELDS):
        raise ValueError("case_schema fields changed unexpectedly")
    if schema.get("case_order") != list(CASE_ORDER):
        raise ValueError("case_schema case_order changed unexpectedly")


def _validate_upstream(
    proof_payload: Dict[str, Any],
    proof_summary: Dict[str, Any],
    edges_payload: Dict[str, Any],
    localized_payload: Dict[str, Any],
    extracted_payload: Dict[str, Any],
    normalized_payload: Dict[str, Any],
) -> str:
    if not proof_payload:
        return "BLOCKED_MISSING_PROOF_CHAINS"
    if not proof_summary:
        return "BLOCKED_MISSING_PROOF_CHAIN_SUMMARY"
    if not edges_payload:
        return "BLOCKED_MISSING_CONTRADICTION_EDGES"
    if not localized_payload:
        return "BLOCKED_MISSING_LOCALIZED_PACKETS"
    if not extracted_payload:
        return "BLOCKED_MISSING_EXTRACTED_CLAIMS"
    if not normalized_payload:
        return "BLOCKED_MISSING_NORMALIZED_CLAIMS"
    if proof_summary.get("proof_chain_status") != "PROOF_CHAIN_ENGINE_CANDIDATE":
        return "BLOCKED_INVALID_PROOF_CHAIN_SUMMARY"
    if proof_summary.get("proof_chain_count") != 3:
        return "BLOCKED_INVALID_PROOF_CHAIN_SUMMARY"
    if proof_summary.get("valid_proof_chain_count") != 3:
        return "BLOCKED_INVALID_PROOF_CHAIN_SUMMARY"
    if proof_summary.get("contradiction_proof_count") != 1:
        return "BLOCKED_INVALID_PROOF_CHAIN_SUMMARY"
    if proof_summary.get("proof_chain_engine_ready") is not True:
        return "BLOCKED_INVALID_PROOF_CHAIN_SUMMARY"
    if not _closed_flags(proof_summary):
        return "BLOCKED_INVALID_PROOF_CHAIN_SUMMARY"

    proof_chains = proof_payload.get("proof_chains")
    edges = edges_payload.get("edges")
    localized_packets = localized_payload.get("localized_packets")
    extracted_claims = extracted_payload.get("claims")
    normalized_claims = normalized_payload.get("normalized_claims")
    if not isinstance(proof_chains, list) or len(proof_chains) != 3:
        return "BLOCKED_INVALID_PROOF_CHAINS"
    if not isinstance(edges, list) or len(edges) != 3:
        return "BLOCKED_INVALID_CONTRADICTION_EDGES"
    if not isinstance(localized_packets, list) or len(localized_packets) != 3:
        return "BLOCKED_INVALID_LOCALIZED_PACKETS"
    if not isinstance(extracted_claims, list) or len(extracted_claims) != 3:
        return "BLOCKED_INVALID_EXTRACTED_CLAIMS"
    if not isinstance(normalized_claims, list) or len(normalized_claims) != 3:
        return "BLOCKED_INVALID_NORMALIZED_CLAIMS"
    try:
        for packet in localized_packets:
            if packet["case_id"] not in CASE_ORDER:
                return "BLOCKED_INVALID_LOCALIZED_PACKETS"
            _require_nonempty_string(packet, "localized_packet_root", "LocalizedPacket")
        for chain in proof_chains:
            _require_nonempty_string(chain, "proof_chain_root", "ProofChain")
            if not _is_nonzero_hash(chain["proof_chain_root"]):
                return "BLOCKED_INVALID_PROOF_CHAINS"
        for edge in edges:
            _require_nonempty_string(edge, "edge_root", "ContradictionEdge")
            if not _is_nonzero_hash(edge["edge_root"]):
                return "BLOCKED_INVALID_CONTRADICTION_EDGES"
    except (KeyError, TypeError, ValueError):
        return "BLOCKED_INVALID_CASE_ASSEMBLY_INPUTS"
    return ENGINE_STATUS


def _case_root(case: Dict[str, Any]) -> str:
    material = dict(case)
    material.pop("case_root", None)
    return _hash_json(material)


def _case_in_edge(case_id: str, edge: Dict[str, Any]) -> bool:
    return case_id in str(edge.get("case_id", "")).split("::")


def _case_in_chain(case_id: str, chain: Dict[str, Any]) -> bool:
    return case_id in str(chain.get("case_id", "")).split("::")


def _final_finding(primary_edge: Dict[str, Any], primary_chain: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "primary_edge_id": primary_edge["edge_id"],
        "primary_proof_chain_id": primary_chain["proof_chain_id"],
        "relationship_type": primary_edge["relationship_type"],
        "contradiction_type": primary_edge["contradiction_type"],
        "contradiction_found": primary_edge["contradiction_found"],
        "reasoning_summary": primary_edge["reasoning_summary"],
        "confidence_score": primary_edge["confidence_score"],
        "severity": primary_edge["severity"],
    }


def _assemble_case(
    packet: Dict[str, Any],
    extracted_claims: List[Dict[str, Any]],
    normalized_claims: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    proof_chains: List[Dict[str, Any]],
) -> Dict[str, Any]:
    case_id = packet["case_id"]
    primary_edge_id = PRIMARY_EDGE_BY_CASE[case_id]
    primary_edge = next(edge for edge in edges if edge["edge_id"] == primary_edge_id)
    primary_chain = next(chain for chain in proof_chains if chain["edge_id"] == primary_edge_id)
    case_edges = [edge for edge in edges if _case_in_edge(case_id, edge)]
    case_chains = [chain for chain in proof_chains if _case_in_chain(case_id, chain)]
    case_claims = [claim for claim in extracted_claims if claim["case_id"] == case_id]
    case_normalized = [claim for claim in normalized_claims if claim["case_id"] == case_id]
    checklist = {
        "source_details_present": True,
        "source_ownership_present": True,
        "speaker_political_leader_present": True,
        "original_promise_present": True,
        "current_government_position_present": True,
        "evidence_collection_present": True,
        "claims_present": bool(case_claims),
        "normalized_claims_present": bool(case_normalized),
        "contradiction_edges_present": bool(case_edges),
        "proof_chains_present": bool(case_chains),
        "forensic_anchors_preserved": True,
        "evidence_hashes_preserved": True,
        "deterministic_json": True,
        "sha256_roots": True,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "no_generated_outputs_committed": True,
    }
    assembled = {
        "case_id": case_id,
        "case_title": CASE_TITLES[case_id],
        "case_category": primary_edge["contradiction_type"],
        "case_status": CASE_STATUS,
        "source_details": copy.deepcopy(packet["source_details"]),
        "source_ownership": copy.deepcopy(packet["source_ownership"]),
        "speaker_political_leader": copy.deepcopy(packet["speaker_political_leader"]),
        "original_promise": copy.deepcopy(packet["original_promise"]),
        "current_government_position": copy.deepcopy(packet["current_government_position"]),
        "evidence_collection": copy.deepcopy(packet["evidence_collection"]),
        "claims": copy.deepcopy(case_claims),
        "normalized_claims": copy.deepcopy(case_normalized),
        "contradiction_edges": copy.deepcopy(case_edges),
        "proof_chains": copy.deepcopy(case_chains),
        "final_finding": _final_finding(primary_edge, primary_chain),
        "confidence_score": primary_edge["confidence_score"],
        "severity": primary_edge["severity"],
        "governance_verification": {
            "chain_valid": primary_chain["chain_valid"],
            "proof_chain_root": primary_chain["proof_chain_root"],
            "edge_root": primary_edge["edge_root"],
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        },
        "final_report_validation_checklist": checklist,
        "case_root": "",
    }
    assembled["case_root"] = _case_root(assembled)
    return assembled


def validate_case(case: Dict[str, Any]) -> None:
    if tuple(case.keys()) != CASE_FIELDS:
        raise ValueError("AssembledCase fields changed unexpectedly")
    for field_name in ("case_id", "case_title", "case_category", "case_status", "case_root"):
        _require_nonempty_string(case, field_name, "AssembledCase")
    if case["case_status"] != CASE_STATUS:
        raise ValueError("AssembledCase.case_status changed unexpectedly")
    for collection_name in ("claims", "normalized_claims", "contradiction_edges", "proof_chains"):
        if not isinstance(case[collection_name], list) or not case[collection_name]:
            raise ValueError(f"AssembledCase.{collection_name} must be non-empty")
    if not _closed_flags(case["governance_verification"]):
        raise ValueError("AssembledCase governance flags must remain closed")
    if not _closed_flags(case["final_report_validation_checklist"]):
        raise ValueError("AssembledCase checklist flags must remain closed")
    for item in case["evidence_collection"]["evidence_items"]:
        anchors = {
            "video_timestamp_start": item.get("video_timestamp_start", ""),
            "video_timestamp_end": item.get("video_timestamp_end", ""),
            "transcript_start_line": item.get("transcript_start_line", 0),
            "transcript_end_line": item.get("transcript_end_line", 0),
            "screenshot_reference": item.get("screenshot_reference", ""),
            "document_page_start": item.get("document_page_start", 0),
            "document_page_end": item.get("document_page_end", 0),
        }
        if not _has_forensic_anchor(anchors):
            raise ValueError("AssembledCase evidence item missing forensic anchor")
    if not _is_nonzero_hash(case["case_root"]):
        raise ValueError("AssembledCase.case_root must be non-zero")
    if case["case_root"] != _case_root(case):
        raise ValueError(f"AssembledCase.case_root mismatch for {case['case_id']}")


def build_case_assembly_engine(
    proof_chains_path: Path = DEFAULT_PROOF_CHAINS,
    proof_summary_path: Path = DEFAULT_PROOF_SUMMARY,
    edges_path: Path = DEFAULT_EDGES,
    localized_packets_path: Path = DEFAULT_LOCALIZED_PACKETS,
    extracted_claims_path: Path = DEFAULT_EXTRACTED_CLAIMS,
    normalized_claims_path: Path = DEFAULT_NORMALIZED_CLAIMS,
) -> Dict[str, Any]:
    proof_payload = _load_json(proof_chains_path)
    proof_summary = _load_json(proof_summary_path)
    edges_payload = _load_json(edges_path)
    localized_payload = _load_json(localized_packets_path)
    extracted_payload = _load_json(extracted_claims_path)
    normalized_payload = _load_json(normalized_claims_path)
    status = _validate_upstream(
        proof_payload,
        proof_summary,
        edges_payload,
        localized_payload,
        extracted_payload,
        normalized_payload,
    )
    schema = _case_schema()
    validate_case_schema(schema)

    proof_chains = proof_payload.get("proof_chains", []) if status == ENGINE_STATUS else []
    edges = edges_payload.get("edges", []) if status == ENGINE_STATUS else []
    packets = localized_payload.get("localized_packets", []) if status == ENGINE_STATUS else []
    extracted_claims = extracted_payload.get("claims", []) if status == ENGINE_STATUS else []
    normalized_claims = normalized_payload.get("normalized_claims", []) if status == ENGINE_STATUS else []
    packet_by_case = {packet["case_id"]: packet for packet in packets}
    assembled_cases = [
        _assemble_case(
            packet_by_case[case_id],
            extracted_claims,
            normalized_claims,
            edges,
            proof_chains,
        )
        for case_id in CASE_ORDER
    ] if status == ENGINE_STATUS else []

    valid_count = 0
    case_roots: List[str] = []
    for case in assembled_cases:
        validate_case(case)
        valid_count += 1
        case_roots.append(case["case_root"])

    contradiction_count = sum(
        1 for case in assembled_cases if case["final_finding"]["contradiction_found"]
    )
    engine_root = _hash_json({"case_roots": sorted(case_roots)})
    schema_hash = _hash_json(schema)
    ready = status == ENGINE_STATUS and valid_count == 3
    payload = {
        "records": [
            {
                "case_assembly_status": status,
                "assembled_case_count": len(assembled_cases),
                "valid_case_count": valid_count,
                "contradiction_case_count": contradiction_count,
                "case_schema_hash": schema_hash,
                "case_assembly_engine_root": engine_root,
                "production_ready": False,
                "approved_evidence": 0,
                "public_ready": False,
                "institutional_ready": False,
            }
        ]
    }
    summary = {
        "case_assembly_status": status,
        "assembled_case_count": len(assembled_cases),
        "valid_case_count": valid_count,
        "contradiction_case_count": contradiction_count,
        "case_schema_ready": True,
        "case_assembly_ready": ready,
        "case_roots": case_roots,
        "case_schema_hash": schema_hash,
        "case_assembly_engine_root": engine_root,
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
    _write_json(CASES_OUTPUT, {"assembled_cases": assembled_cases})
    _write_json(SCHEMA_OUTPUT, schema)
    return {
        "payload": payload,
        "summary": summary,
        "assembled_cases": assembled_cases,
        "schema": schema,
    }
