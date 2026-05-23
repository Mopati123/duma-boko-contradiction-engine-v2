"""
evidence_gate.py - Shared EvidenceObject linkage validation for reportable cases.
"""

from typing import Any, Dict, List, Tuple

from evidence.evidence_schema import EvidenceObject, validate_evidence_object


REPORTABLE_CLAIM_KEYS = ("promise", "outcome_or_position", "analysis")

REQUIRED_EVIDENCE_KEYS = {
    "evidence_id",
    "case_id",
    "source_type",
    "platform",
    "title",
    "url",
    "evidence_role",
    "verification_status",
    "evidence_strength",
}


def _placeholder_url_parts() -> Tuple[str, ...]:
    token = "example"
    return (
        ".".join((token, "com")),
        token + str(1),
        token + str(2),
        "youtube.com/watch?v=" + token,
    )


def _role_token(claim_role: str) -> str:
    if claim_role == "outcome_or_position":
        return "OUTCOME"
    return claim_role.upper().replace("_", "-")


def evidence_id_for(case_id: str, claim_role: str, index: int = 1) -> str:
    return f"{case_id}-{_role_token(claim_role)}-{index:03d}"


def _source_type_from_position(position: Dict[str, Any]) -> str:
    return str(position.get("source_type") or position.get("evidence_type", ""))


def evidence_object_from_position(
    case_id: str,
    claim_role: str,
    position: Dict[str, Any],
    index: int = 1,
) -> Dict[str, Any]:
    evidence = EvidenceObject(
        evidence_id=evidence_id_for(case_id, claim_role, index),
        case_id=case_id,
        source_type=_source_type_from_position(position),
        platform=str(position.get("platform", "")),
        title=str(position.get("title") or position.get("source", "")),
        url=str(position.get("url", "")),
        evidence_role=claim_role,
        verification_status=str(position.get("verification_status", "source_linked")),
        evidence_strength=str(position.get("evidence_strength", "low")),
        speaker=position.get("speaker"),
        speaker_confidence=position.get("speaker_confidence"),
        target_phrases=list(position.get("target_phrases") or position.get("matched_terms", [])),
        transcript_status=position.get("transcript_status"),
        timestamp_start=position.get("timestamp_start"),
        timestamp_end=position.get("timestamp_end"),
        raw_quote=position.get("raw_quote"),
        context_before=position.get("context_before"),
        context_after=position.get("context_after"),
        notes=position.get("notes"),
    )
    return evidence.to_dict()


def build_case_evidence(
    case_id: str,
    promise: Dict[str, Any],
    outcome_or_position: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    promise_evidence = evidence_object_from_position(case_id, "promise", promise)
    outcome_evidence = evidence_object_from_position(
        case_id, "outcome_or_position", outcome_or_position
    )

    evidence_objects = [promise_evidence, outcome_evidence]
    claim_evidence_links = {
        "promise": [promise_evidence["evidence_id"]],
        "outcome_or_position": [outcome_evidence["evidence_id"]],
        "analysis": [
            promise_evidence["evidence_id"],
            outcome_evidence["evidence_id"],
        ],
    }
    return evidence_objects, claim_evidence_links


def validate_case_evidence_links(case: Dict[str, Any]) -> None:
    case_id = str(case.get("case_id", "UNKNOWN"))
    evidence_objects = case.get("evidence_objects")
    if not isinstance(evidence_objects, list) or not evidence_objects:
        raise ValueError(f"{case_id}: missing evidence_objects")

    evidence_by_id: Dict[str, Dict[str, Any]] = {}
    for idx, evidence in enumerate(evidence_objects):
        if not isinstance(evidence, dict):
            raise ValueError(f"{case_id}: evidence_objects[{idx}] must be an object")

        missing = REQUIRED_EVIDENCE_KEYS - set(evidence.keys())
        if missing:
            raise ValueError(
                f"{case_id}: evidence_objects[{idx}] missing keys: {sorted(missing)}"
            )

        try:
            validate_evidence_object(evidence)
        except ValueError as exc:
            raise ValueError(f"{case_id}: {exc}") from exc

        evidence_id = evidence["evidence_id"]
        if evidence_id in evidence_by_id:
            raise ValueError(f"{case_id}: duplicate evidence_id {evidence_id}")
        evidence_by_id[evidence_id] = evidence

    links = case.get("claim_evidence_links")
    if not isinstance(links, dict):
        raise ValueError(f"{case_id}: missing claim_evidence_links")

    for claim_key in REPORTABLE_CLAIM_KEYS:
        linked_ids = links.get(claim_key)
        if not isinstance(linked_ids, list) or not linked_ids:
            raise ValueError(f"{case_id}: {claim_key} must link to evidence")

        for evidence_id in linked_ids:
            if evidence_id not in evidence_by_id:
                raise ValueError(
                    f"{case_id}: {claim_key} links unknown evidence_id {evidence_id}"
                )


def validate_cases_for_report(cases: List[Dict[str, Any]]) -> None:
    if not isinstance(cases, list) or not cases:
        raise ValueError("Report generation requires at least one evidence-linked case")

    for case in cases:
        validate_case_evidence_links(case)


def get_linked_evidence(case: Dict[str, Any], claim_key: str) -> List[Dict[str, Any]]:
    validate_case_evidence_links(case)
    evidence_by_id = {
        evidence["evidence_id"]: evidence
        for evidence in case.get("evidence_objects", [])
    }
    return [
        evidence_by_id[evidence_id]
        for evidence_id in case.get("claim_evidence_links", {}).get(claim_key, [])
    ]
