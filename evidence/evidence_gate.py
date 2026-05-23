"""
evidence_gate.py - Shared EvidenceObject linkage validation for reportable cases.
"""

from typing import Any, Dict, List, Tuple

from evidence.evidence_schema import EvidenceObject


REPORTABLE_CLAIM_KEYS = ("promise", "outcome_or_position", "analysis")

REQUIRED_EVIDENCE_KEYS = {
    "evidence_id",
    "case_id",
    "claim_role",
    "quote",
    "source",
    "url",
    "date",
    "evidence_type",
    "platform",
    "verification_status",
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


def evidence_object_from_position(
    case_id: str,
    claim_role: str,
    position: Dict[str, Any],
    index: int = 1,
) -> Dict[str, Any]:
    evidence = EvidenceObject(
        evidence_id=evidence_id_for(case_id, claim_role, index),
        case_id=case_id,
        claim_role=claim_role,
        quote=str(position.get("quote", "")),
        source=str(position.get("source", "")),
        url=str(position.get("url", "")),
        date=str(position.get("date", "")),
        evidence_type=str(position.get("evidence_type", "")),
        platform=str(position.get("platform", "")),
        verification_status=str(position.get("verification_status", "source_linked")),
        timestamp_start=position.get("timestamp_start"),
        timestamp_end=position.get("timestamp_end"),
        screenshot_path=position.get("screenshot_path"),
        confidence=float(position.get("confidence", 0.0) or 0.0),
        speaker=str(position.get("speaker", "Duma Boko")),
        matched_terms=list(position.get("matched_terms", [])),
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


def _require_nonempty_string(value: Any, field_name: str, case_id: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{case_id}: evidence field {field_name} must be non-empty")


def _reject_placeholder_url(url: str, case_id: str) -> None:
    normalized_url = url.lower()
    for placeholder in _placeholder_url_parts():
        if placeholder in normalized_url:
            raise ValueError(
                f"{case_id}: evidence URL appears to be a placeholder: {url}"
            )


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

        for field_name in REQUIRED_EVIDENCE_KEYS:
            _require_nonempty_string(evidence.get(field_name), field_name, case_id)

        _reject_placeholder_url(evidence["url"], case_id)

        verification_status = evidence["verification_status"].strip()
        has_timestamp = bool(evidence.get("timestamp_start") or evidence.get("timestamp_end"))
        if verification_status == "timestamp_verified" and not has_timestamp:
            raise ValueError(
                f"{case_id}: timestamp_verified evidence requires timestamp fields"
            )

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
