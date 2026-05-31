#!/usr/bin/env python3
"""
Claim Normalization Engine v2.

Builds deterministic normalized sample claims from extracted claim records. The
normalized claims are schema/demo records only; they are not approved evidence
and they do not mark production, public, or institutional readiness.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import copy
import hashlib
import json


DEFAULT_EXTRACTED_CLAIMS = Path("outputs/claim_extraction_engine/extracted_claims.json")
DEFAULT_EXTRACTION_SUMMARY = Path(
    "outputs/claim_extraction_engine/claim_extraction_summary.json"
)
DEFAULT_CLAIM_SCHEMA = Path("outputs/claim_extraction_engine/claim_schema.json")

DEFAULT_OUTPUT_DIR = Path("outputs/claim_normalization_engine")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "claim_normalization_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "claim_normalization_summary.json"
NORMALIZED_CLAIMS_OUTPUT = DEFAULT_OUTPUT_DIR / "normalized_claims.json"
NORMALIZED_SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "normalized_claim_schema.json"

ENGINE_STATUS = "CLAIM_NORMALIZATION_ENGINE_CANDIDATE"
SCHEMA_VERSION = "claim_normalization_engine_v2"
UPSTREAM_SCHEMA_VERSION = "claim_extraction_engine_v2"
NORMALIZATION_STATUS = "candidate_normalized_claim"
NORMALIZATION_METHOD = "deterministic_sample_normalization"

CANONICAL_DOMAINS = (
    "EMPLOYMENT",
    "POLICY_IMPLEMENTATION",
    "GOVERNMENT_POSITION",
)

CANONICAL_ACTIONS = (
    "CREATE",
    "STATE_POSITION",
    "DOCUMENT_STATUS",
    "IMPLEMENT",
    "NOT_IMPLEMENT",
    "UNKNOWN",
)

POLARITIES = (
    "AFFIRMATIVE",
    "NEGATIVE",
    "UNKNOWN",
)

NORMALIZED_CLAIM_FIELDS = (
    "normalized_claim_id",
    "claim_id",
    "case_id",
    "packet_id",
    "original_claim_type",
    "normalized_claim_type",
    "original_claim_category",
    "normalized_domain",
    "normalized_subject",
    "normalized_action",
    "normalized_target",
    "normalized_timeframe",
    "canonical_meaning",
    "comparison_key",
    "polarity",
    "evidence_anchors",
    "evidence_hashes",
    "normalization_confidence",
    "normalization_method",
    "source_claim_root",
    "normalized_claim_root",
    "normalization_status",
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

NORMALIZATION_MAPPING = {
    "CASE_SAMPLE_001": {
        "normalized_claim_id": "NORMALIZED_CLAIM_SAMPLE_001",
        "normalized_claim_type": "PROMISE",
        "normalized_domain": "EMPLOYMENT",
        "normalized_subject": "employment",
        "normalized_action": "CREATE",
        "normalized_target": "100000_jobs",
        "normalized_timeframe": "5_years",
        "canonical_meaning": "EMPLOYMENT_CREATE_100000_JOBS_WITHIN_5_YEARS",
        "comparison_key": "EMPLOYMENT::100000_JOBS::5_YEARS",
        "polarity": "AFFIRMATIVE",
    },
    "CASE_SAMPLE_002": {
        "normalized_claim_id": "NORMALIZED_CLAIM_SAMPLE_002",
        "normalized_claim_type": "CURRENT_POSITION",
        "normalized_domain": "EMPLOYMENT",
        "normalized_subject": "employment_programme",
        "normalized_action": "STATE_POSITION",
        "normalized_target": "employment_programme_status",
        "normalized_timeframe": "UNSPECIFIED",
        "canonical_meaning": "EMPLOYMENT_PROGRAMME_STATUS_POSITION",
        "comparison_key": "EMPLOYMENT::EMPLOYMENT_PROGRAMME_STATUS::UNSPECIFIED",
        "polarity": "AFFIRMATIVE",
    },
    "CASE_SAMPLE_003": {
        "normalized_claim_id": "NORMALIZED_CLAIM_SAMPLE_003",
        "normalized_claim_type": "IMPLEMENTATION_STATUS",
        "normalized_domain": "POLICY_IMPLEMENTATION",
        "normalized_subject": "policy_implementation",
        "normalized_action": "DOCUMENT_STATUS",
        "normalized_target": "policy_implementation_evidence",
        "normalized_timeframe": "UNSPECIFIED",
        "canonical_meaning": "POLICY_IMPLEMENTATION_STATUS_DOCUMENTED",
        "comparison_key": "POLICY_IMPLEMENTATION::POLICY_IMPLEMENTATION_EVIDENCE::UNSPECIFIED",
        "polarity": "AFFIRMATIVE",
    },
}


@dataclass
class NormalizedClaim:
    normalized_claim_id: str
    claim_id: str
    case_id: str
    packet_id: str
    original_claim_type: str
    normalized_claim_type: str
    original_claim_category: str
    normalized_domain: str
    normalized_subject: str
    normalized_action: str
    normalized_target: str
    normalized_timeframe: str
    canonical_meaning: str
    comparison_key: str
    polarity: str
    evidence_anchors: Dict[str, Any]
    evidence_hashes: List[str]
    normalization_confidence: float
    normalization_method: str
    source_claim_root: str
    normalized_claim_root: str
    normalization_status: str

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


def _normalized_claim_schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "normalized_claim_fields": list(NORMALIZED_CLAIM_FIELDS),
        "canonical_domains": list(CANONICAL_DOMAINS),
        "canonical_actions": list(CANONICAL_ACTIONS),
        "polarities": list(POLARITIES),
        "evidence_anchor_fields": list(EVIDENCE_ANCHOR_FIELDS),
        "normalization_method": NORMALIZATION_METHOD,
        "normalization_status": NORMALIZATION_STATUS,
        "root_rules": {
            "normalized_claim_root": (
                "sha256 over normalized claim content excluding normalized_claim_root"
            ),
            "claim_normalization_engine_root": "sha256 over sorted normalized claim roots",
        },
        "closed_governance_flags": {
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        },
    }


def validate_normalized_claim_schema(schema: Dict[str, Any]) -> None:
    if schema.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("normalized_claim_schema schema_version changed unexpectedly")
    if schema.get("normalized_claim_fields") != list(NORMALIZED_CLAIM_FIELDS):
        raise ValueError("normalized_claim_schema fields changed unexpectedly")
    if schema.get("canonical_domains") != list(CANONICAL_DOMAINS):
        raise ValueError("normalized_claim_schema canonical_domains changed unexpectedly")
    if schema.get("canonical_actions") != list(CANONICAL_ACTIONS):
        raise ValueError("normalized_claim_schema canonical_actions changed unexpectedly")
    if schema.get("evidence_anchor_fields") != list(EVIDENCE_ANCHOR_FIELDS):
        raise ValueError("normalized_claim_schema evidence_anchor_fields changed unexpectedly")


def _validate_upstream(
    extracted_payload: Dict[str, Any],
    extraction_summary: Dict[str, Any],
    claim_schema: Dict[str, Any],
) -> str:
    if not extracted_payload:
        return "BLOCKED_MISSING_EXTRACTED_CLAIMS"
    if not extraction_summary:
        return "BLOCKED_MISSING_CLAIM_EXTRACTION_SUMMARY"
    if not claim_schema:
        return "BLOCKED_MISSING_CLAIM_SCHEMA"
    if extraction_summary.get("claim_extraction_status") != "CLAIM_EXTRACTION_ENGINE_CANDIDATE":
        return "BLOCKED_INVALID_CLAIM_EXTRACTION_SUMMARY"
    if extraction_summary.get("claim_count") != 3:
        return "BLOCKED_INVALID_CLAIM_EXTRACTION_SUMMARY"
    if extraction_summary.get("valid_claim_count") != 3:
        return "BLOCKED_INVALID_CLAIM_EXTRACTION_SUMMARY"
    if extraction_summary.get("invalid_claim_count") != 0:
        return "BLOCKED_INVALID_CLAIM_EXTRACTION_SUMMARY"
    if extraction_summary.get("claim_schema_ready") is not True:
        return "BLOCKED_INVALID_CLAIM_EXTRACTION_SUMMARY"
    if extraction_summary.get("claim_extraction_ready") is not True:
        return "BLOCKED_INVALID_CLAIM_EXTRACTION_SUMMARY"
    if not _is_nonzero_hash(extraction_summary.get("claim_extraction_engine_root")):
        return "BLOCKED_INVALID_CLAIM_EXTRACTION_SUMMARY"
    if not _closed_flags(extraction_summary):
        return "BLOCKED_INVALID_CLAIM_EXTRACTION_SUMMARY"
    if claim_schema.get("schema_version") != UPSTREAM_SCHEMA_VERSION:
        return "BLOCKED_INVALID_CLAIM_SCHEMA"

    claims = extracted_payload.get("claims")
    if not isinstance(claims, list) or len(claims) != 3:
        return "BLOCKED_INVALID_EXTRACTED_CLAIMS"
    try:
        for claim in claims:
            for field_name in (
                "claim_id",
                "case_id",
                "packet_id",
                "claim_type",
                "claim_category",
                "claim_root",
            ):
                _require_nonempty_string(claim, field_name, "Claim")
            if not _is_nonzero_hash(claim.get("claim_root")):
                return "BLOCKED_INVALID_EXTRACTED_CLAIMS"
            anchors = claim.get("evidence_anchors")
            if not isinstance(anchors, dict):
                return "BLOCKED_INVALID_EXTRACTED_CLAIMS"
            if set(anchors.keys()) != set(EVIDENCE_ANCHOR_FIELDS):
                return "BLOCKED_INVALID_EXTRACTED_CLAIMS"
            if not _has_forensic_anchor(anchors):
                return "BLOCKED_INVALID_EXTRACTED_CLAIMS"
            evidence_hashes = claim.get("evidence_hashes")
            if not isinstance(evidence_hashes, list) or not evidence_hashes:
                return "BLOCKED_INVALID_EXTRACTED_CLAIMS"
            for evidence_hash in evidence_hashes:
                if not _is_nonzero_hash(evidence_hash):
                    return "BLOCKED_INVALID_EXTRACTED_CLAIMS"
    except (TypeError, ValueError):
        return "BLOCKED_INVALID_EXTRACTED_CLAIMS"
    return ENGINE_STATUS


def _normalized_claim_root_material(claim: NormalizedClaim) -> Dict[str, Any]:
    data = claim.to_dict()
    data.pop("normalized_claim_root", None)
    return data


def _assign_normalized_claim_root(claim: NormalizedClaim) -> NormalizedClaim:
    claim.normalized_claim_root = _hash_json(_normalized_claim_root_material(claim))
    return claim


def _normalized_claim_for_claim(claim: Dict[str, Any]) -> NormalizedClaim:
    case_id = claim["case_id"]
    if case_id not in NORMALIZATION_MAPPING:
        raise ValueError(f"Unsupported sample case_id for claim normalization: {case_id}")
    mapping = NORMALIZATION_MAPPING[case_id]
    normalized_claim = NormalizedClaim(
        normalized_claim_id=mapping["normalized_claim_id"],
        claim_id=claim["claim_id"],
        case_id=case_id,
        packet_id=claim["packet_id"],
        original_claim_type=claim["claim_type"],
        normalized_claim_type=mapping["normalized_claim_type"],
        original_claim_category=claim["claim_category"],
        normalized_domain=mapping["normalized_domain"],
        normalized_subject=mapping["normalized_subject"],
        normalized_action=mapping["normalized_action"],
        normalized_target=mapping["normalized_target"],
        normalized_timeframe=mapping["normalized_timeframe"],
        canonical_meaning=mapping["canonical_meaning"],
        comparison_key=mapping["comparison_key"],
        polarity=mapping["polarity"],
        evidence_anchors=copy.deepcopy(claim["evidence_anchors"]),
        evidence_hashes=list(claim["evidence_hashes"]),
        normalization_confidence=1.0,
        normalization_method=NORMALIZATION_METHOD,
        source_claim_root=claim["claim_root"],
        normalized_claim_root="",
        normalization_status=NORMALIZATION_STATUS,
    )
    return _assign_normalized_claim_root(normalized_claim)


def validate_normalized_claim(
    normalized_claim: Any,
    source_claims_by_id: Dict[str, Dict[str, Any]],
) -> None:
    data = (
        normalized_claim.to_dict()
        if hasattr(normalized_claim, "to_dict")
        else normalized_claim
    )
    if not isinstance(data, dict):
        raise ValueError("NormalizedClaim must be a dictionary-like value")
    if tuple(data.keys()) != NORMALIZED_CLAIM_FIELDS:
        raise ValueError("NormalizedClaim fields changed unexpectedly")
    for field_name in (
        "normalized_claim_id",
        "claim_id",
        "case_id",
        "packet_id",
        "original_claim_type",
        "normalized_claim_type",
        "original_claim_category",
        "normalized_domain",
        "normalized_subject",
        "normalized_action",
        "normalized_target",
        "normalized_timeframe",
        "canonical_meaning",
        "comparison_key",
        "polarity",
        "normalization_method",
        "source_claim_root",
        "normalized_claim_root",
        "normalization_status",
    ):
        _require_nonempty_string(data, field_name, "NormalizedClaim")
    if data["claim_id"] not in source_claims_by_id:
        raise ValueError(f"NormalizedClaim references unknown claim_id: {data['claim_id']}")
    source_claim = source_claims_by_id[data["claim_id"]]
    if data["source_claim_root"] != source_claim["claim_root"]:
        raise ValueError("NormalizedClaim.source_claim_root must match source claim root")
    if data["normalized_domain"] not in CANONICAL_DOMAINS:
        raise ValueError(f"Unsupported normalized_domain: {data['normalized_domain']}")
    if data["normalized_action"] not in CANONICAL_ACTIONS:
        raise ValueError(f"Unsupported normalized_action: {data['normalized_action']}")
    if data["polarity"] not in POLARITIES:
        raise ValueError(f"Unsupported polarity: {data['polarity']}")
    if data["normalization_confidence"] != 1.0:
        raise ValueError("NormalizedClaim.normalization_confidence must be deterministic 1.0")
    if data["normalization_method"] != NORMALIZATION_METHOD:
        raise ValueError("NormalizedClaim.normalization_method changed unexpectedly")
    if data["normalization_status"] != NORMALIZATION_STATUS:
        raise ValueError("NormalizedClaim.normalization_status changed unexpectedly")
    if data["evidence_anchors"] != source_claim["evidence_anchors"]:
        raise ValueError("NormalizedClaim.evidence_anchors must match source claim")
    if data["evidence_hashes"] != source_claim["evidence_hashes"]:
        raise ValueError("NormalizedClaim.evidence_hashes must match source claim")
    if not isinstance(data["evidence_hashes"], list) or not data["evidence_hashes"]:
        raise ValueError("NormalizedClaim.evidence_hashes must be non-empty")
    if not _has_forensic_anchor(data["evidence_anchors"]):
        raise ValueError("NormalizedClaim must preserve a forensic anchor")
    if not _is_nonzero_hash(data["normalized_claim_root"]):
        raise ValueError("NormalizedClaim.normalized_claim_root must be non-zero")
    expected_root = _hash_json(
        {key: value for key, value in data.items() if key != "normalized_claim_root"}
    )
    if data["normalized_claim_root"] != expected_root:
        raise ValueError(
            f"NormalizedClaim.normalized_claim_root mismatch for {data['normalized_claim_id']}"
        )


def build_claim_normalization_engine(
    extracted_claims_path: Path = DEFAULT_EXTRACTED_CLAIMS,
    extraction_summary_path: Path = DEFAULT_EXTRACTION_SUMMARY,
    claim_schema_path: Path = DEFAULT_CLAIM_SCHEMA,
) -> Dict[str, Any]:
    extracted_payload = _load_json(extracted_claims_path)
    extraction_summary = _load_json(extraction_summary_path)
    claim_schema = _load_json(claim_schema_path)
    status = _validate_upstream(extracted_payload, extraction_summary, claim_schema)
    schema = _normalized_claim_schema()
    validate_normalized_claim_schema(schema)

    source_claims = extracted_payload.get("claims", []) if status == ENGINE_STATUS else []
    normalized_claims = [_normalized_claim_for_claim(claim) for claim in source_claims]
    normalized_claim_dicts = [claim.to_dict() for claim in normalized_claims]
    source_claims_by_id = {claim["claim_id"]: claim for claim in source_claims}

    valid_count = 0
    invalid_count = 0
    normalized_roots: List[str] = []
    for normalized_claim in normalized_claim_dicts:
        try:
            validate_normalized_claim(normalized_claim, source_claims_by_id)
            valid_count += 1
        except ValueError:
            invalid_count += 1
            raise
        normalized_roots.append(normalized_claim["normalized_claim_root"])

    normalized_claim_ids = {claim["claim_id"] for claim in normalized_claim_dicts}
    source_claim_ids = {claim["claim_id"] for claim in source_claims}
    if status == ENGINE_STATUS and normalized_claim_ids != source_claim_ids:
        raise ValueError("Every extracted claim must produce exactly one normalized claim")

    ready = status == ENGINE_STATUS and valid_count == 3 and invalid_count == 0
    engine_root = _hash_json({"normalized_claim_roots": sorted(normalized_roots)})
    schema_hash = _hash_json(schema)
    payload = {
        "records": [
            {
                "claim_normalization_status": status,
                "input_claim_count": len(source_claims),
                "normalized_claim_count": len(normalized_claim_dicts),
                "valid_normalized_claim_count": valid_count,
                "invalid_normalized_claim_count": invalid_count,
                "normalized_claim_schema_hash": schema_hash,
                "claim_normalization_engine_root": engine_root,
                "production_ready": False,
                "approved_evidence": 0,
                "public_ready": False,
                "institutional_ready": False,
            }
        ]
    }
    summary = {
        "claim_normalization_status": status,
        "input_claim_count": len(source_claims),
        "normalized_claim_count": len(normalized_claim_dicts),
        "valid_normalized_claim_count": valid_count,
        "invalid_normalized_claim_count": invalid_count,
        "normalized_claim_schema_ready": True,
        "claim_normalization_ready": ready,
        "normalized_claim_roots": normalized_roots,
        "normalized_claim_schema_hash": schema_hash,
        "claim_normalization_engine_root": engine_root,
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
    _write_json(NORMALIZED_CLAIMS_OUTPUT, {"normalized_claims": normalized_claim_dicts})
    _write_json(NORMALIZED_SCHEMA_OUTPUT, schema)
    return {
        "payload": payload,
        "summary": summary,
        "normalized_claims": normalized_claim_dicts,
        "schema": schema,
    }
