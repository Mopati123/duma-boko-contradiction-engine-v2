"""
evidence_loader.py - Load and normalize EvidenceObject seed records.
"""

from pathlib import Path
from typing import Any, Dict, List

import yaml

from evidence.evidence_schema import EvidenceObject, save_json, validate_evidence_object


DEFAULT_SEED_PATH = Path("data/evidence_seed/videos.yaml")
DEFAULT_INDEX_PATH = Path("outputs/evidence/evidence_index.json")


def _seed_record_to_evidence_object(evidence_id: str, record: Dict[str, Any]) -> EvidenceObject:
    return EvidenceObject(
        evidence_id=evidence_id,
        case_id=str(record.get("case_id", "")),
        source_type=str(record.get("source_type", "")),
        platform=str(record.get("platform", "")),
        title=str(record.get("title", "")),
        url=str(record.get("url", "")),
        evidence_role=str(record.get("evidence_role", "")),
        verification_status=str(record.get("verification_status", "")),
        evidence_strength=str(record.get("evidence_strength", "")),
        speaker=record.get("speaker"),
        speaker_confidence=record.get("speaker_confidence"),
        target_phrases=list(record.get("target_phrases", [])),
        transcript_status=record.get("transcript_status"),
        timestamp_start=record.get("timestamp_start"),
        timestamp_end=record.get("timestamp_end"),
        raw_quote=record.get("raw_quote"),
        context_before=record.get("context_before"),
        context_after=record.get("context_after"),
        notes=record.get("notes"),
    )


def load_seed_evidence(seed_path: Path = DEFAULT_SEED_PATH) -> List[EvidenceObject]:
    with seed_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Evidence seed file must contain a mapping: {seed_path}")

    evidence_objects: List[EvidenceObject] = []
    for evidence_id, record in data.items():
        if not isinstance(record, dict):
            raise ValueError(f"Evidence seed record must be an object: {evidence_id}")

        evidence = _seed_record_to_evidence_object(str(evidence_id), record)
        validate_evidence_object(evidence)
        evidence_objects.append(evidence)

    return evidence_objects


def build_evidence_index(
    seed_path: Path = DEFAULT_SEED_PATH,
    output_path: Path = DEFAULT_INDEX_PATH,
) -> Dict[str, Any]:
    evidence_objects = load_seed_evidence(seed_path)
    index = {
        "metadata": {
            "schema_version": "EvidenceObject.v1",
            "source": str(seed_path),
            "total_evidence_records": len(evidence_objects),
        },
        "evidence": [evidence.to_dict() for evidence in evidence_objects],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(index, str(output_path))
    return index
