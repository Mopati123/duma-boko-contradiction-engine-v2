#!/usr/bin/env python3
"""
Contradiction Graph Engine v2.

Builds deterministic sample contradiction relationships from normalized claim
records. The graph is schema/demo evidence only; it is not approved evidence and
does not mark production, public, or institutional readiness.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import copy
import hashlib
import json


DEFAULT_NORMALIZED_CLAIMS = Path(
    "outputs/claim_normalization_engine/normalized_claims.json"
)
DEFAULT_NORMALIZATION_SUMMARY = Path(
    "outputs/claim_normalization_engine/claim_normalization_summary.json"
)
DEFAULT_NORMALIZED_SCHEMA = Path(
    "outputs/claim_normalization_engine/normalized_claim_schema.json"
)

DEFAULT_OUTPUT_DIR = Path("outputs/contradiction_graph_engine")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "contradiction_graph_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "contradiction_graph_summary.json"
GRAPH_OUTPUT = DEFAULT_OUTPUT_DIR / "contradiction_graph.json"
EDGES_OUTPUT = DEFAULT_OUTPUT_DIR / "contradiction_edges.json"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "contradiction_graph_schema.json"

ENGINE_STATUS = "CONTRADICTION_GRAPH_ENGINE_CANDIDATE"
SCHEMA_VERSION = "contradiction_graph_engine_v2"
UPSTREAM_SCHEMA_VERSION = "claim_normalization_engine_v2"
EDGE_STATUS = "candidate_sample_edge"

RELATIONSHIP_TYPES = (
    "SUPPORTS",
    "CONTRADICTS",
    "INSUFFICIENT_EVIDENCE",
    "RELATED",
)

CONTRADICTION_TYPES = (
    "PROMISE_VS_CURRENT_POSITION",
    "PROMISE_VS_IMPLEMENTATION_STATUS",
    "POLICY_POSITION_MISMATCH",
    "NONE",
)

SEVERITIES = (
    "HIGH",
    "MEDIUM",
    "LOW",
)

EDGE_FIELDS = (
    "edge_id",
    "case_id",
    "source_claim_id",
    "target_claim_id",
    "source_normalized_claim_id",
    "target_normalized_claim_id",
    "source_domain",
    "target_domain",
    "source_action",
    "target_action",
    "source_comparison_key",
    "target_comparison_key",
    "relationship_type",
    "contradiction_type",
    "contradiction_found",
    "severity",
    "confidence_score",
    "reasoning_summary",
    "evidence_anchors",
    "evidence_hashes",
    "source_claim_root",
    "target_claim_root",
    "edge_root",
    "edge_status",
)

NODE_FIELDS = (
    "normalized_claim_id",
    "claim_id",
    "case_id",
    "normalized_domain",
    "normalized_action",
    "comparison_key",
    "normalized_claim_root",
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

EDGE_MAPPING = (
    {
        "edge_id": "EDGE_SAMPLE_001_002",
        "source_case_id": "CASE_SAMPLE_001",
        "target_case_id": "CASE_SAMPLE_002",
        "relationship_type": "CONTRADICTS",
        "contradiction_type": "PROMISE_VS_CURRENT_POSITION",
        "contradiction_found": True,
        "severity": "HIGH",
        "confidence_score": 0.86,
        "reasoning_summary": (
            "Sample employment promise is compared with a sample current-position "
            "statement and marked as a deterministic contradiction example."
        ),
    },
    {
        "edge_id": "EDGE_SAMPLE_001_003",
        "source_case_id": "CASE_SAMPLE_001",
        "target_case_id": "CASE_SAMPLE_003",
        "relationship_type": "RELATED",
        "contradiction_type": "PROMISE_VS_IMPLEMENTATION_STATUS",
        "contradiction_found": False,
        "severity": "MEDIUM",
        "confidence_score": 0.72,
        "reasoning_summary": (
            "Sample employment promise and sample implementation status are related "
            "but do not establish a contradiction in this schema sample."
        ),
    },
    {
        "edge_id": "EDGE_SAMPLE_002_003",
        "source_case_id": "CASE_SAMPLE_002",
        "target_case_id": "CASE_SAMPLE_003",
        "relationship_type": "SUPPORTS",
        "contradiction_type": "NONE",
        "contradiction_found": False,
        "severity": "LOW",
        "confidence_score": 0.68,
        "reasoning_summary": (
            "Sample current-position and implementation-status records are marked "
            "as mutually supportive for graph schema validation."
        ),
    },
)


@dataclass
class ContradictionEdge:
    edge_id: str
    case_id: str
    source_claim_id: str
    target_claim_id: str
    source_normalized_claim_id: str
    target_normalized_claim_id: str
    source_domain: str
    target_domain: str
    source_action: str
    target_action: str
    source_comparison_key: str
    target_comparison_key: str
    relationship_type: str
    contradiction_type: str
    contradiction_found: bool
    severity: str
    confidence_score: float
    reasoning_summary: str
    evidence_anchors: Dict[str, Any]
    evidence_hashes: Dict[str, Any]
    source_claim_root: str
    target_claim_root: str
    edge_root: str
    edge_status: str

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


def _contradiction_graph_schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "edge_fields": list(EDGE_FIELDS),
        "node_fields": list(NODE_FIELDS),
        "relationship_types": list(RELATIONSHIP_TYPES),
        "contradiction_types": list(CONTRADICTION_TYPES),
        "severities": list(SEVERITIES),
        "evidence_anchor_fields": list(EVIDENCE_ANCHOR_FIELDS),
        "edge_status": EDGE_STATUS,
        "root_rules": {
            "edge_root": "sha256 over edge content excluding edge_root",
            "contradiction_graph_root": "sha256 over sorted edge roots",
        },
        "closed_governance_flags": {
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        },
    }


def validate_contradiction_graph_schema(schema: Dict[str, Any]) -> None:
    if schema.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("contradiction_graph_schema schema_version changed unexpectedly")
    if schema.get("edge_fields") != list(EDGE_FIELDS):
        raise ValueError("contradiction_graph_schema edge_fields changed unexpectedly")
    if schema.get("node_fields") != list(NODE_FIELDS):
        raise ValueError("contradiction_graph_schema node_fields changed unexpectedly")
    if schema.get("relationship_types") != list(RELATIONSHIP_TYPES):
        raise ValueError("contradiction_graph_schema relationship_types changed unexpectedly")
    if schema.get("contradiction_types") != list(CONTRADICTION_TYPES):
        raise ValueError("contradiction_graph_schema contradiction_types changed unexpectedly")


def _validate_upstream(
    normalized_payload: Dict[str, Any],
    normalization_summary: Dict[str, Any],
    normalized_schema: Dict[str, Any],
) -> str:
    if not normalized_payload:
        return "BLOCKED_MISSING_NORMALIZED_CLAIMS"
    if not normalization_summary:
        return "BLOCKED_MISSING_CLAIM_NORMALIZATION_SUMMARY"
    if not normalized_schema:
        return "BLOCKED_MISSING_NORMALIZED_CLAIM_SCHEMA"
    if (
        normalization_summary.get("claim_normalization_status")
        != "CLAIM_NORMALIZATION_ENGINE_CANDIDATE"
    ):
        return "BLOCKED_INVALID_CLAIM_NORMALIZATION_SUMMARY"
    if normalization_summary.get("input_claim_count") != 3:
        return "BLOCKED_INVALID_CLAIM_NORMALIZATION_SUMMARY"
    if normalization_summary.get("normalized_claim_count") != 3:
        return "BLOCKED_INVALID_CLAIM_NORMALIZATION_SUMMARY"
    if normalization_summary.get("valid_normalized_claim_count") != 3:
        return "BLOCKED_INVALID_CLAIM_NORMALIZATION_SUMMARY"
    if normalization_summary.get("invalid_normalized_claim_count") != 0:
        return "BLOCKED_INVALID_CLAIM_NORMALIZATION_SUMMARY"
    if normalization_summary.get("claim_normalization_ready") is not True:
        return "BLOCKED_INVALID_CLAIM_NORMALIZATION_SUMMARY"
    if normalization_summary.get("normalized_claim_schema_ready") is not True:
        return "BLOCKED_INVALID_CLAIM_NORMALIZATION_SUMMARY"
    if not _is_nonzero_hash(normalization_summary.get("claim_normalization_engine_root")):
        return "BLOCKED_INVALID_CLAIM_NORMALIZATION_SUMMARY"
    if not _closed_flags(normalization_summary):
        return "BLOCKED_INVALID_CLAIM_NORMALIZATION_SUMMARY"
    if normalized_schema.get("schema_version") != UPSTREAM_SCHEMA_VERSION:
        return "BLOCKED_INVALID_NORMALIZED_CLAIM_SCHEMA"

    claims = normalized_payload.get("normalized_claims")
    if not isinstance(claims, list) or len(claims) != 3:
        return "BLOCKED_INVALID_NORMALIZED_CLAIMS"
    try:
        for claim in claims:
            for field_name in (
                "normalized_claim_id",
                "claim_id",
                "case_id",
                "normalized_domain",
                "normalized_action",
                "comparison_key",
                "normalized_claim_root",
            ):
                _require_nonempty_string(claim, field_name, "NormalizedClaim")
            if not _is_nonzero_hash(claim.get("normalized_claim_root")):
                return "BLOCKED_INVALID_NORMALIZED_CLAIMS"
            anchors = claim.get("evidence_anchors")
            if not isinstance(anchors, dict):
                return "BLOCKED_INVALID_NORMALIZED_CLAIMS"
            if set(anchors.keys()) != set(EVIDENCE_ANCHOR_FIELDS):
                return "BLOCKED_INVALID_NORMALIZED_CLAIMS"
            if not _has_forensic_anchor(anchors):
                return "BLOCKED_INVALID_NORMALIZED_CLAIMS"
            evidence_hashes = claim.get("evidence_hashes")
            if not isinstance(evidence_hashes, list) or not evidence_hashes:
                return "BLOCKED_INVALID_NORMALIZED_CLAIMS"
            for evidence_hash in evidence_hashes:
                if not _is_nonzero_hash(evidence_hash):
                    return "BLOCKED_INVALID_NORMALIZED_CLAIMS"
    except (TypeError, ValueError):
        return "BLOCKED_INVALID_NORMALIZED_CLAIMS"
    return ENGINE_STATUS


def _edge_root_material(edge: ContradictionEdge) -> Dict[str, Any]:
    data = edge.to_dict()
    data.pop("edge_root", None)
    return data


def _assign_edge_root(edge: ContradictionEdge) -> ContradictionEdge:
    edge.edge_root = _hash_json(_edge_root_material(edge))
    return edge


def _edge_for_mapping(
    mapping: Dict[str, Any],
    claims_by_case_id: Dict[str, Dict[str, Any]],
) -> ContradictionEdge:
    source = claims_by_case_id[mapping["source_case_id"]]
    target = claims_by_case_id[mapping["target_case_id"]]
    edge = ContradictionEdge(
        edge_id=mapping["edge_id"],
        case_id=f"{source['case_id']}::{target['case_id']}",
        source_claim_id=source["claim_id"],
        target_claim_id=target["claim_id"],
        source_normalized_claim_id=source["normalized_claim_id"],
        target_normalized_claim_id=target["normalized_claim_id"],
        source_domain=source["normalized_domain"],
        target_domain=target["normalized_domain"],
        source_action=source["normalized_action"],
        target_action=target["normalized_action"],
        source_comparison_key=source["comparison_key"],
        target_comparison_key=target["comparison_key"],
        relationship_type=mapping["relationship_type"],
        contradiction_type=mapping["contradiction_type"],
        contradiction_found=mapping["contradiction_found"],
        severity=mapping["severity"],
        confidence_score=mapping["confidence_score"],
        reasoning_summary=mapping["reasoning_summary"],
        evidence_anchors={
            "source": copy.deepcopy(source["evidence_anchors"]),
            "target": copy.deepcopy(target["evidence_anchors"]),
        },
        evidence_hashes={
            "source": list(source["evidence_hashes"]),
            "target": list(target["evidence_hashes"]),
        },
        source_claim_root=source["normalized_claim_root"],
        target_claim_root=target["normalized_claim_root"],
        edge_root="",
        edge_status=EDGE_STATUS,
    )
    return _assign_edge_root(edge)


def _node_for_claim(claim: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "normalized_claim_id": claim["normalized_claim_id"],
        "claim_id": claim["claim_id"],
        "case_id": claim["case_id"],
        "normalized_domain": claim["normalized_domain"],
        "normalized_action": claim["normalized_action"],
        "comparison_key": claim["comparison_key"],
        "normalized_claim_root": claim["normalized_claim_root"],
    }


def validate_edge(
    edge: Any,
    claims_by_normalized_id: Dict[str, Dict[str, Any]],
) -> None:
    data = edge.to_dict() if hasattr(edge, "to_dict") else edge
    if not isinstance(data, dict):
        raise ValueError("ContradictionEdge must be a dictionary-like value")
    if tuple(data.keys()) != EDGE_FIELDS:
        raise ValueError("ContradictionEdge fields changed unexpectedly")
    for field_name in (
        "edge_id",
        "case_id",
        "source_claim_id",
        "target_claim_id",
        "source_normalized_claim_id",
        "target_normalized_claim_id",
        "source_domain",
        "target_domain",
        "source_action",
        "target_action",
        "source_comparison_key",
        "target_comparison_key",
        "relationship_type",
        "contradiction_type",
        "severity",
        "reasoning_summary",
        "source_claim_root",
        "target_claim_root",
        "edge_root",
        "edge_status",
    ):
        _require_nonempty_string(data, field_name, "ContradictionEdge")
    if data["relationship_type"] not in RELATIONSHIP_TYPES:
        raise ValueError(f"Unsupported relationship_type: {data['relationship_type']}")
    if data["contradiction_type"] not in CONTRADICTION_TYPES:
        raise ValueError(f"Unsupported contradiction_type: {data['contradiction_type']}")
    if data["severity"] not in SEVERITIES:
        raise ValueError(f"Unsupported severity: {data['severity']}")
    if data["edge_status"] != EDGE_STATUS:
        raise ValueError("ContradictionEdge.edge_status changed unexpectedly")
    if not isinstance(data["contradiction_found"], bool):
        raise ValueError("ContradictionEdge.contradiction_found must be boolean")
    if not isinstance(data["confidence_score"], float):
        raise ValueError("ContradictionEdge.confidence_score must be float")

    source = claims_by_normalized_id.get(data["source_normalized_claim_id"])
    target = claims_by_normalized_id.get(data["target_normalized_claim_id"])
    if not source or not target:
        raise ValueError("ContradictionEdge references unknown normalized claim")
    if data["source_claim_id"] != source["claim_id"]:
        raise ValueError("ContradictionEdge.source_claim_id mismatch")
    if data["target_claim_id"] != target["claim_id"]:
        raise ValueError("ContradictionEdge.target_claim_id mismatch")
    if data["source_domain"] != source["normalized_domain"]:
        raise ValueError("ContradictionEdge.source_domain mismatch")
    if data["target_domain"] != target["normalized_domain"]:
        raise ValueError("ContradictionEdge.target_domain mismatch")
    if data["source_action"] != source["normalized_action"]:
        raise ValueError("ContradictionEdge.source_action mismatch")
    if data["target_action"] != target["normalized_action"]:
        raise ValueError("ContradictionEdge.target_action mismatch")
    if data["source_comparison_key"] != source["comparison_key"]:
        raise ValueError("ContradictionEdge.source_comparison_key mismatch")
    if data["target_comparison_key"] != target["comparison_key"]:
        raise ValueError("ContradictionEdge.target_comparison_key mismatch")
    if data["source_claim_root"] != source["normalized_claim_root"]:
        raise ValueError("ContradictionEdge.source_claim_root mismatch")
    if data["target_claim_root"] != target["normalized_claim_root"]:
        raise ValueError("ContradictionEdge.target_claim_root mismatch")
    if data["evidence_anchors"] != {
        "source": source["evidence_anchors"],
        "target": target["evidence_anchors"],
    }:
        raise ValueError("ContradictionEdge.evidence_anchors must preserve source and target")
    if data["evidence_hashes"] != {
        "source": source["evidence_hashes"],
        "target": target["evidence_hashes"],
    }:
        raise ValueError("ContradictionEdge.evidence_hashes must preserve source and target")
    if not _has_forensic_anchor(data["evidence_anchors"]["source"]):
        raise ValueError("ContradictionEdge source anchors are invalid")
    if not _has_forensic_anchor(data["evidence_anchors"]["target"]):
        raise ValueError("ContradictionEdge target anchors are invalid")
    if not _is_nonzero_hash(data["edge_root"]):
        raise ValueError("ContradictionEdge.edge_root must be non-zero")
    expected_root = _hash_json({key: value for key, value in data.items() if key != "edge_root"})
    if data["edge_root"] != expected_root:
        raise ValueError(f"ContradictionEdge.edge_root mismatch for {data['edge_id']}")


def build_contradiction_graph_engine(
    normalized_claims_path: Path = DEFAULT_NORMALIZED_CLAIMS,
    normalization_summary_path: Path = DEFAULT_NORMALIZATION_SUMMARY,
    normalized_schema_path: Path = DEFAULT_NORMALIZED_SCHEMA,
) -> Dict[str, Any]:
    normalized_payload = _load_json(normalized_claims_path)
    normalization_summary = _load_json(normalization_summary_path)
    normalized_schema = _load_json(normalized_schema_path)
    status = _validate_upstream(normalized_payload, normalization_summary, normalized_schema)
    schema = _contradiction_graph_schema()
    validate_contradiction_graph_schema(schema)

    normalized_claims = (
        normalized_payload.get("normalized_claims", []) if status == ENGINE_STATUS else []
    )
    claims_by_case_id = {claim["case_id"]: claim for claim in normalized_claims}
    claims_by_normalized_id = {
        claim["normalized_claim_id"]: claim for claim in normalized_claims
    }
    edges = (
        [_edge_for_mapping(mapping, claims_by_case_id) for mapping in EDGE_MAPPING]
        if status == ENGINE_STATUS
        else []
    )
    edge_dicts = [edge.to_dict() for edge in edges]

    valid_count = 0
    invalid_count = 0
    edge_roots: List[str] = []
    for edge in edge_dicts:
        try:
            validate_edge(edge, claims_by_normalized_id)
            valid_count += 1
        except ValueError:
            invalid_count += 1
            raise
        edge_roots.append(edge["edge_root"])

    contradiction_count = sum(1 for edge in edge_dicts if edge["contradiction_found"])
    support_count = sum(1 for edge in edge_dicts if edge["relationship_type"] == "SUPPORTS")
    related_count = sum(1 for edge in edge_dicts if edge["relationship_type"] == "RELATED")
    if status == ENGINE_STATUS and contradiction_count < 1:
        raise ValueError("At least one sample contradiction must be found")

    graph_root = _hash_json({"edge_roots": sorted(edge_roots)})
    schema_hash = _hash_json(schema)
    ready = status == ENGINE_STATUS and valid_count == 3 and invalid_count == 0
    nodes = [_node_for_claim(claim) for claim in normalized_claims]
    graph = {
        "nodes": nodes,
        "edges": edge_dicts,
        "graph_root": graph_root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
    }
    payload = {
        "records": [
            {
                "contradiction_graph_status": status,
                "normalized_claim_count": len(normalized_claims),
                "edge_count": len(edge_dicts),
                "contradiction_count": contradiction_count,
                "support_count": support_count,
                "related_count": related_count,
                "valid_edge_count": valid_count,
                "invalid_edge_count": invalid_count,
                "contradiction_graph_schema_hash": schema_hash,
                "contradiction_graph_root": graph_root,
                "production_ready": False,
                "approved_evidence": 0,
                "public_ready": False,
                "institutional_ready": False,
            }
        ]
    }
    summary = {
        "contradiction_graph_status": status,
        "normalized_claim_count": len(normalized_claims),
        "edge_count": len(edge_dicts),
        "contradiction_count": contradiction_count,
        "support_count": support_count,
        "related_count": related_count,
        "valid_edge_count": valid_count,
        "invalid_edge_count": invalid_count,
        "contradiction_graph_schema_ready": True,
        "contradiction_graph_ready": ready,
        "edge_roots": edge_roots,
        "contradiction_graph_schema_hash": schema_hash,
        "contradiction_graph_root": graph_root,
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
    _write_json(GRAPH_OUTPUT, graph)
    _write_json(EDGES_OUTPUT, {"edges": edge_dicts})
    _write_json(SCHEMA_OUTPUT, schema)
    return {
        "payload": payload,
        "summary": summary,
        "graph": graph,
        "edges": edge_dicts,
        "schema": schema,
    }
