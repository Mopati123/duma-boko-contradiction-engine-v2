#!/usr/bin/env python3
"""
Manual AFTER Snapshot Claim Extraction v2.

Extracts conservative manual-review claim candidates from manual AFTER snapshot
evidence packets. This lane does not invent claims, normalize claims, create
embeddings, create contradictions, fetch URLs, read refused snapshots, create
proof chains, create final reports, mark production readiness, or approve
evidence.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json
import re


DEFAULT_PACKETS = Path(
    "outputs/manual_after_snapshot_to_evidence_packets/"
    "manual_after_snapshot_evidence_packets.json"
)
DEFAULT_PACKET_SUMMARY = Path(
    "outputs/manual_after_snapshot_to_evidence_packets/"
    "manual_after_snapshot_packet_summary.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/manual_after_snapshot_claim_extraction")
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_after_snapshot_claim_summary.json"
CLAIMS_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_after_snapshot_claims.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_after_snapshot_claim_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "manual_after_snapshot_claim_report.md"

SCHEMA_VERSION = "manual_after_snapshot_claim_extraction_v2"
UPSTREAM_SCHEMA_VERSION = "manual_after_snapshot_to_evidence_packets_v2"

DRY_RUN_STATUS = "MANUAL_AFTER_SNAPSHOT_CLAIM_EXTRACTION_DRY_RUN_VALIDATED"
CANDIDATE_STATUS = "MANUAL_AFTER_SNAPSHOT_CLAIM_EXTRACTION_CANDIDATE"
PARTIAL_STATUS = "MANUAL_AFTER_SNAPSHOT_CLAIM_EXTRACTION_PARTIAL"
REFUSED_STATUS = "MANUAL_AFTER_SNAPSHOT_CLAIM_EXTRACTION_REFUSED"

UPSTREAM_STATUSES = (
    "MANUAL_AFTER_SNAPSHOT_PACKET_DRY_RUN_VALIDATED",
    "MANUAL_AFTER_SNAPSHOT_PACKET_CANDIDATE",
    "MANUAL_AFTER_SNAPSHOT_PACKET_PARTIAL",
    "MANUAL_AFTER_SNAPSHOT_PACKET_REFUSED",
)
TIME_DIRECTION = "AFTER"
SOURCE_TYPE = "MANUAL_AFTER_SOURCE_SNAPSHOT"

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
CLAIM_TYPES = (
    "POLICY_STATEMENT",
    "PUBLIC_STATUS",
    "PROJECT_DELIVERY_STATUS",
    "ECONOMIC_DEVELOPMENT_STATEMENT",
    "ENERGY_TRANSITION_STATEMENT",
    "UNKNOWN_CLAIM",
)
CLAIM_FIELDS = (
    "manual_after_snapshot_claim_id",
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
    "claim_text",
    "claim_type",
    "claim_category",
    "claim_confidence",
    "packet_hash",
    "packet_root",
    "manual_review_required",
    "claim_root",
)
REFUSAL_FIELDS = (
    "refusal_id",
    "manual_after_snapshot_packet_id",
    "snapshot_id",
    "linked_after_candidate_id",
    "url",
    "claim_text",
    "refusal_code",
    "refusal_reason",
    "packet_hash",
    "packet_root",
    "manual_review_required",
    "production_ready",
    "approved_evidence",
    "public_ready",
    "institutional_ready",
    "refusal_root",
)
REFUSAL_CODES = (
    "REFUSED_EMPTY_TEXT",
    "REFUSED_NAVIGATION_OR_BOILERPLATE",
    "REFUSED_HEADING_ONLY",
    "REFUSED_NO_EXPLICIT_CLAIM",
    "REFUSED_MALFORMED_PACKET",
    "REFUSED_NON_AFTER_PACKET",
    "REFUSED_NON_MANUAL_AFTER_SOURCE",
    "REFUSED_HASH_OR_ROOT_MISMATCH",
    "REFUSED_INVALID_UPSTREAM_GUARDRAILS",
    "REFUSED_DUPLICATE_PACKET_ID",
)

TERMINAL_SENTENCE_PATTERN = re.compile(r"[^.!?]+(?:[.!?]+|$)")
DATE_PREFIX_PATTERN = re.compile(
    r"^(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+"
    r"\d{1,2},\s+\d{4}\.$",
    re.IGNORECASE,
)
DECLARATIVE_VERB_PATTERN = re.compile(
    r"\b(is|are|was|were|has|have|had|will|would|can|could|should|represents|"
    r"marked|marks|stated|emphasised|emphasized|said|says|signing|signed|"
    r"implemented|implements|executed|enable|enables|inject|injects|increase|"
    r"reduce|reduces|lower|lowers|stimulate|stimulates|create|creates|"
    r"developed|operated|accelerates|builds|become|becomes|positioned)\b",
    re.IGNORECASE,
)
PROJECT_PATTERN = re.compile(
    r"\b(project|plant|groundbreaking|ceremony|power purchase agreement|ppa|"
    r"500mw|500mwh|bess|battery energy storage|photovoltaic|pv|completion|"
    r"operational|commissioning|commissioned|developed|independent power producer|"
    r"construction|implemented|executed|flagship development)\b",
    re.IGNORECASE,
)
ENERGY_PATTERN = re.compile(
    r"\b(energy|renewable|solar|grid|electricity|generation|energy security|"
    r"transition|national generation mix|integrated resource plan|regional energy hub|"
    r"power exports|solar irradiation|sunshine|clean and reliable energy|storage)\b",
    re.IGNORECASE,
)
ECONOMIC_PATTERN = re.compile(
    r"\b(investment|imports|carbon footprint|citizen participation|green economy|"
    r"economic transformation|economic|development|sustainable development|"
    r"investment inflows|opportunities|climate action)\b",
    re.IGNORECASE,
)
POLICY_PATTERN = re.compile(
    r"\b(policy|plan|framework|programme|program|initiative|partnership|"
    r"government to government|resource plan|model|agreement|commitment|"
    r"national|strategy)\b",
    re.IGNORECASE,
)
PUBLIC_STATUS_PATTERN = re.compile(
    r"\b(president|officiating|government|botswana power corporation|"
    r"okavango solar|sultanate of oman|duma boko|david kgoboko|stated|"
    r"emphasised|emphasized)\b",
    re.IGNORECASE,
)
BOILERPLATE_PHRASES = (
    "all rights reserved",
    "cookie policy",
    "privacy policy",
    "subscribe",
    "follow us",
    "share this",
    "read more",
    "skip to content",
)
NAVIGATION_TERMS = {
    "home",
    "news",
    "contact",
    "about",
    "search",
    "menu",
    "gallery",
    "videos",
    "facebook",
    "twitter",
    "youtube",
}


class ManualAfterSnapshotClaimRefusal(ValueError):
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


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string.")


def _packet_hash_material(packet: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: packet[field]
        for field in PACKET_FIELDS
        if field not in ("packet_hash", "packet_root")
    }


def _packet_root_material(packet: Dict[str, Any]) -> Dict[str, Any]:
    return {field: packet[field] for field in PACKET_FIELDS if field != "packet_root"}


def _claim_root_material(claim: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(claim)
    material.pop("claim_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+", text))


def _schema_payload() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "upstream_schema_version": UPSTREAM_SCHEMA_VERSION,
        "manual_after_snapshot_claim_extraction_only": True,
        "modes": ["dry-run", "extract-claims"],
        "upstream_statuses": list(UPSTREAM_STATUSES),
        "packet_fields": list(PACKET_FIELDS),
        "claim_fields": list(CLAIM_FIELDS),
        "claim_types": list(CLAIM_TYPES),
        "refusal_fields": list(REFUSAL_FIELDS),
        "refusal_codes": list(REFUSAL_CODES),
        "extraction_rule": (
            "Claim text is copied exactly from deterministic sentence-like chunks "
            "of manual AFTER snapshot packet evidence_text after trimming outer "
            "whitespace. No rewriting, summarizing, normalization, or inference "
            "is performed."
        ),
        "root_rules": {
            "packet_hash": "validated sha256 over upstream packet excluding packet_hash and packet_root",
            "packet_root": "validated sha256 over upstream packet excluding packet_root",
            "claim_root": "sha256 over manual AFTER snapshot claim excluding claim_root",
            "refusal_root": "sha256 over manual AFTER snapshot claim refusal excluding refusal_root",
        },
        "closed_guardrails": {
            "approved_evidence": 0,
            "claims_invented": 0,
            "claims_normalized": 0,
            "embeddings_created": 0,
            "contradictions_created": 0,
            "proof_chains_created": 0,
            "final_reports_created": 0,
            "urls_fetched": 0,
            "production_ready": False,
        },
    }


def _load_packets(packets_path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(packets_path)
    if not isinstance(payload, dict) or not payload:
        raise ValueError("manual_after_snapshot_evidence_packets.json is missing.")
    if payload.get("schema_version") != UPSTREAM_SCHEMA_VERSION:
        raise ValueError("manual_after_snapshot_evidence_packets schema_version is unsupported.")
    packets = payload.get("manual_after_snapshot_evidence_packets")
    if not isinstance(packets, list):
        raise ValueError("manual_after_snapshot_evidence_packets must be a list.")
    return packets


def _validate_upstream_summary(summary_path: Path, packet_count: int) -> Dict[str, Any]:
    summary = _load_json(summary_path)
    if not isinstance(summary, dict) or not summary:
        raise ValueError("manual_after_snapshot_packet_summary.json is missing.")
    if summary.get("manual_after_snapshot_packet_status") not in UPSTREAM_STATUSES:
        raise ValueError("Manual AFTER snapshot packet upstream status is invalid.")
    if summary.get("manual_after_snapshot_packet_count") != packet_count:
        raise ValueError("Manual AFTER snapshot packet count does not match summary.")
    for counter_name in (
        "urls_fetched",
        "text_invented",
        "claims_created",
        "contradictions_created",
        "proof_chains_created",
        "final_reports_created",
    ):
        if summary.get(counter_name) != 0:
            raise ManualAfterSnapshotClaimRefusal(
                "REFUSED_INVALID_UPSTREAM_GUARDRAILS",
                f"Upstream guardrail {counter_name} must remain 0.",
            )
    for flag_name in (
        "lineage_preserved",
        "snapshot_id_preserved",
        "source_metadata_preserved",
        "snapshot_text_hash_preserved",
        "metadata_hash_preserved",
        "snapshot_root_preserved",
        "evidence_text_exact_copy",
        "no_generated_outputs_committed",
    ):
        if summary.get(flag_name) is not True:
            raise ManualAfterSnapshotClaimRefusal(
                "REFUSED_INVALID_UPSTREAM_GUARDRAILS",
                f"Upstream preservation flag {flag_name} must remain true.",
            )
    if not _closed_flags(summary):
        raise ManualAfterSnapshotClaimRefusal(
            "REFUSED_INVALID_UPSTREAM_GUARDRAILS",
            "Manual AFTER snapshot packet governance flags must remain closed.",
        )
    return summary


def _validate_packet(packet: Dict[str, Any]) -> None:
    if not isinstance(packet, dict) or set(packet.keys()) != set(PACKET_FIELDS):
        raise ManualAfterSnapshotClaimRefusal(
            "REFUSED_MALFORMED_PACKET",
            "Manual AFTER snapshot evidence packet fields do not match upstream schema.",
        )
    for field_name in PACKET_FIELDS:
        if field_name == "manual_review_required":
            continue
        _require_nonempty_string(packet, field_name, "ManualAfterSnapshotEvidencePacket")
    if packet["time_direction"] != TIME_DIRECTION:
        raise ManualAfterSnapshotClaimRefusal(
            "REFUSED_NON_AFTER_PACKET",
            "Manual AFTER snapshot evidence packet time_direction must remain AFTER.",
        )
    if packet["source_type"] != SOURCE_TYPE:
        raise ManualAfterSnapshotClaimRefusal(
            "REFUSED_NON_MANUAL_AFTER_SOURCE",
            "Manual AFTER snapshot evidence packet source_type is unsupported.",
        )
    if packet["manual_review_required"] is not True:
        raise ManualAfterSnapshotClaimRefusal(
            "REFUSED_MALFORMED_PACKET",
            "Manual AFTER snapshot evidence packet manual_review_required must remain true.",
        )
    for hash_field in ("snapshot_text_hash", "metadata_hash", "snapshot_root", "packet_hash", "packet_root"):
        if not _is_nonzero_hash(packet.get(hash_field)):
            raise ManualAfterSnapshotClaimRefusal(
                "REFUSED_HASH_OR_ROOT_MISMATCH",
                f"Manual AFTER snapshot packet missing preserved {hash_field}.",
            )
    if packet["snapshot_text_hash"] != _sha256_text(packet["evidence_text"]):
        raise ManualAfterSnapshotClaimRefusal(
            "REFUSED_HASH_OR_ROOT_MISMATCH",
            "Manual AFTER snapshot packet snapshot_text_hash does not match evidence_text.",
        )
    if packet["packet_hash"] != _hash_json(_packet_hash_material(packet)):
        raise ManualAfterSnapshotClaimRefusal(
            "REFUSED_HASH_OR_ROOT_MISMATCH",
            "Manual AFTER snapshot packet_hash mismatch.",
        )
    if packet["packet_root"] != _hash_json(_packet_root_material(packet)):
        raise ManualAfterSnapshotClaimRefusal(
            "REFUSED_HASH_OR_ROOT_MISMATCH",
            "Manual AFTER snapshot packet_root mismatch.",
        )


def _split_claim_chunks(text: str) -> List[str]:
    raw_chunks: List[str] = []
    for match in TERMINAL_SENTENCE_PATTERN.finditer(text):
        chunk = match.group(0).strip()
        if chunk:
            raw_chunks.append(chunk)
    chunks: List[str] = []
    index = 0
    while index < len(raw_chunks):
        chunk = raw_chunks[index]
        if DATE_PREFIX_PATTERN.fullmatch(chunk) and index + 1 < len(raw_chunks):
            chunks.append(f"{chunk} {raw_chunks[index + 1]}")
            index += 2
            continue
        chunks.append(chunk)
        index += 1
    return chunks


def _is_navigation_or_boilerplate(text: str) -> bool:
    lowered = re.sub(r"\s+", " ", text.strip().lower())
    if lowered in NAVIGATION_TERMS:
        return True
    if any(phrase in lowered for phrase in BOILERPLATE_PHRASES):
        return True
    if re.fullmatch(r"https?://\S+", lowered):
        return True
    if _word_count(lowered) <= 3 and not DECLARATIVE_VERB_PATTERN.search(lowered):
        return True
    return False


def _is_heading_only(text: str) -> bool:
    stripped = text.strip()
    if _word_count(stripped) <= 4 and not re.search(r"[.!?]", stripped):
        return True
    if len(stripped) <= 120 and stripped == stripped.upper() and not re.search(r"[.!?]$", stripped):
        return True
    if not DECLARATIVE_VERB_PATTERN.search(stripped) and _word_count(stripped) <= 8:
        return True
    return False


def _has_explicit_statement(text: str) -> bool:
    stripped = text.strip()
    return bool(
        DECLARATIVE_VERB_PATTERN.search(stripped)
        or PROJECT_PATTERN.search(stripped)
        or ENERGY_PATTERN.search(stripped)
        or ECONOMIC_PATTERN.search(stripped)
    ) and _word_count(stripped) >= 5


def _claim_type_for_text(text: str) -> Optional[str]:
    stripped = text.strip()
    if not stripped or _word_count(stripped) < 5:
        return None
    if _is_navigation_or_boilerplate(stripped) or _is_heading_only(stripped):
        return None
    if not _has_explicit_statement(stripped):
        return None
    if PROJECT_PATTERN.search(stripped):
        return "PROJECT_DELIVERY_STATUS"
    if ENERGY_PATTERN.search(stripped):
        return "ENERGY_TRANSITION_STATEMENT"
    if ECONOMIC_PATTERN.search(stripped):
        return "ECONOMIC_DEVELOPMENT_STATEMENT"
    if POLICY_PATTERN.search(stripped):
        return "POLICY_STATEMENT"
    if PUBLIC_STATUS_PATTERN.search(stripped):
        return "PUBLIC_STATUS"
    return "UNKNOWN_CLAIM"


def _claim_confidence_for_type(claim_type: str) -> float:
    return {
        "POLICY_STATEMENT": 0.62,
        "PUBLIC_STATUS": 0.64,
        "PROJECT_DELIVERY_STATUS": 0.74,
        "ECONOMIC_DEVELOPMENT_STATEMENT": 0.68,
        "ENERGY_TRANSITION_STATEMENT": 0.70,
        "UNKNOWN_CLAIM": 0.45,
    }[claim_type]


def _claim_category_for_type(claim_type: str) -> str:
    return {
        "POLICY_STATEMENT": "manual_after_snapshot_policy_statement",
        "PUBLIC_STATUS": "manual_after_snapshot_public_status",
        "PROJECT_DELIVERY_STATUS": "manual_after_snapshot_project_delivery_status",
        "ECONOMIC_DEVELOPMENT_STATEMENT": "manual_after_snapshot_economic_development_statement",
        "ENERGY_TRANSITION_STATEMENT": "manual_after_snapshot_energy_transition_statement",
        "UNKNOWN_CLAIM": "manual_after_snapshot_unknown_claim",
    }[claim_type]


def _make_claim(packet: Dict[str, Any], claim_index: int, claim_text: str, claim_type: str) -> Dict[str, Any]:
    claim = {
        "manual_after_snapshot_claim_id": f"MANUAL_AFTER_SNAPSHOT_CLAIM_{claim_index:06d}",
        "manual_after_snapshot_packet_id": packet["manual_after_snapshot_packet_id"],
        "snapshot_id": packet["snapshot_id"],
        "linked_after_candidate_id": packet["linked_after_candidate_id"],
        "after_stability_target_id": packet["after_stability_target_id"],
        "linked_before_claim_id": packet["linked_before_claim_id"],
        "target_theme": packet["target_theme"],
        "target_evidence_type": packet["target_evidence_type"],
        "preferred_source_family": packet["preferred_source_family"],
        "time_direction": packet["time_direction"],
        "source_type": packet["source_type"],
        "url": packet["url"],
        "title": packet["title"],
        "publisher": packet["publisher"],
        "published_date": packet["published_date"],
        "claim_text": claim_text,
        "claim_type": claim_type,
        "claim_category": _claim_category_for_type(claim_type),
        "claim_confidence": _claim_confidence_for_type(claim_type),
        "packet_hash": packet["packet_hash"],
        "packet_root": packet["packet_root"],
        "manual_review_required": True,
        "claim_root": "",
    }
    claim["claim_root"] = _hash_json(_claim_root_material(claim))
    return claim


def _packet_identity(packet: Any) -> Tuple[str, str, str, str]:
    if not isinstance(packet, dict):
        return ("UNKNOWN_PACKET", "UNKNOWN_SNAPSHOT", "UNKNOWN_CANDIDATE", "")
    return (
        str(packet.get("manual_after_snapshot_packet_id") or "UNKNOWN_PACKET"),
        str(packet.get("snapshot_id") or "UNKNOWN_SNAPSHOT"),
        str(packet.get("linked_after_candidate_id") or "UNKNOWN_CANDIDATE"),
        str(packet.get("url") or ""),
    )


def _make_refusal(packet: Any, claim_text: str, code: str, reason: str) -> Dict[str, Any]:
    packet_id, snapshot_id, linked_after_candidate_id, url = _packet_identity(packet)
    packet_hash = str(packet.get("packet_hash") or "") if isinstance(packet, dict) else ""
    packet_root = str(packet.get("packet_root") or "") if isinstance(packet, dict) else ""
    refusal = {
        "refusal_id": f"MANUAL_AFTER_SNAPSHOT_CLAIM_REFUSAL_{packet_id}_{_sha256_text(claim_text)[:12]}",
        "manual_after_snapshot_packet_id": packet_id,
        "snapshot_id": snapshot_id,
        "linked_after_candidate_id": linked_after_candidate_id,
        "url": url,
        "claim_text": claim_text,
        "refusal_code": code,
        "refusal_reason": reason,
        "packet_hash": packet_hash,
        "packet_root": packet_root,
        "manual_review_required": True,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def _refusal_for_text(text: str) -> Tuple[str, str]:
    if not text.strip():
        return "REFUSED_EMPTY_TEXT", "Manual AFTER snapshot claim chunk is empty."
    if _is_navigation_or_boilerplate(text):
        return "REFUSED_NAVIGATION_OR_BOILERPLATE", "Claim chunk is navigation or boilerplate."
    if _is_heading_only(text):
        return "REFUSED_HEADING_ONLY", "Claim chunk is heading-only text."
    return "REFUSED_NO_EXPLICIT_CLAIM", "Claim chunk lacks an explicit factual, policy, project, economic, energy, or status statement."


def validate_claim(claim: Dict[str, Any], valid_packet_ids: List[str]) -> None:
    if tuple(claim.keys()) != CLAIM_FIELDS:
        raise ValueError("Manual AFTER snapshot claim fields changed unexpectedly.")
    for field_name in (
        "manual_after_snapshot_claim_id",
        "manual_after_snapshot_packet_id",
        "snapshot_id",
        "linked_after_candidate_id",
        "time_direction",
        "source_type",
        "url",
        "title",
        "publisher",
        "published_date",
        "claim_text",
        "claim_type",
        "claim_category",
        "packet_hash",
        "packet_root",
        "claim_root",
    ):
        _require_nonempty_string(claim, field_name, "ManualAfterSnapshotClaim")
    if claim["manual_after_snapshot_packet_id"] not in valid_packet_ids:
        raise ValueError("Manual AFTER snapshot claim references an unknown packet.")
    if claim["time_direction"] != TIME_DIRECTION:
        raise ValueError("Manual AFTER snapshot claim time_direction must remain AFTER.")
    if claim["source_type"] != SOURCE_TYPE:
        raise ValueError("Manual AFTER snapshot claim source_type is unsupported.")
    if claim["claim_type"] not in CLAIM_TYPES:
        raise ValueError("Manual AFTER snapshot claim claim_type unsupported.")
    if not isinstance(claim["claim_confidence"], float):
        raise ValueError("Manual AFTER snapshot claim confidence must be a float.")
    if claim["claim_confidence"] < 0 or claim["claim_confidence"] > 1:
        raise ValueError("Manual AFTER snapshot claim confidence must be between 0 and 1.")
    if not _is_nonzero_hash(claim["packet_hash"]) or not _is_nonzero_hash(claim["packet_root"]):
        raise ValueError("Manual AFTER snapshot claim must preserve packet hash/root.")
    if claim["manual_review_required"] is not True:
        raise ValueError("Manual AFTER snapshot claim manual_review_required must remain true.")
    if claim["claim_root"] != _hash_json(_claim_root_material(claim)):
        raise ValueError(f"claim_root mismatch for {claim['manual_after_snapshot_claim_id']}.")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if tuple(refusal.keys()) != REFUSAL_FIELDS:
        raise ValueError("Manual AFTER snapshot claim refusal fields changed unexpectedly.")
    for field_name in (
        "refusal_id",
        "manual_after_snapshot_packet_id",
        "snapshot_id",
        "linked_after_candidate_id",
        "refusal_code",
        "refusal_reason",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "ManualAfterSnapshotClaimRefusal")
    if refusal["refusal_code"] not in REFUSAL_CODES:
        raise ValueError("Manual AFTER snapshot claim refusal_code unsupported.")
    if refusal["manual_review_required"] is not True:
        raise ValueError("Manual AFTER snapshot claim refusal manual_review_required must remain true.")
    if not _closed_flags(refusal):
        raise ValueError("Manual AFTER snapshot claim refusal guardrails must remain closed.")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}.")


def _claims_or_refusals(
    packet: Dict[str, Any],
    next_claim_index: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    try:
        _validate_packet(packet)
    except ManualAfterSnapshotClaimRefusal as exc:
        refusal = _make_refusal(packet, str(packet.get("evidence_text") or ""), exc.code, exc.reason)
        validate_refusal(refusal)
        return [], [refusal]
    except ValueError as exc:
        refusal = _make_refusal(
            packet,
            str(packet.get("evidence_text") or "") if isinstance(packet, dict) else "",
            "REFUSED_MALFORMED_PACKET",
            str(exc),
        )
        validate_refusal(refusal)
        return [], [refusal]

    claims: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    chunks = _split_claim_chunks(packet["evidence_text"])
    if not chunks:
        refusal = _make_refusal(packet, "", "REFUSED_EMPTY_TEXT", "Manual AFTER snapshot evidence_text produced no claim chunks.")
        validate_refusal(refusal)
        return [], [refusal]

    for chunk in chunks:
        claim_type = _claim_type_for_text(chunk)
        if claim_type is None:
            code, reason = _refusal_for_text(chunk)
            refusal = _make_refusal(packet, chunk, code, reason)
            validate_refusal(refusal)
            refusals.append(refusal)
            continue
        claim = _make_claim(packet, next_claim_index + len(claims), chunk, claim_type)
        claims.append(claim)
    return claims, refusals


def _status_for(mode: str, claim_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    if claim_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if claim_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    return REFUSED_STATUS


def _summary_root_material(summary: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {
        "manual_after_snapshot_claim_root",
        "manual_after_snapshot_claim_schema_hash",
        "manual_after_snapshot_claim_report_hash",
    }
    return {key: value for key, value in summary.items() if key not in excluded}


def _build_report(
    status: str,
    mode: str,
    packet_count: int,
    claims: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    claim_lines = ["- None"]
    if claims:
        claim_lines = []
        for claim in claims[:20]:
            preview = claim["claim_text"][:160].replace("\n", " ")
            claim_lines.extend(
                [
                    f"- {claim['manual_after_snapshot_claim_id']}: {claim['claim_type']}",
                    f"  - Packet: {claim['manual_after_snapshot_packet_id']}",
                    f"  - Snapshot: {claim['snapshot_id']}",
                    f"  - Text Preview: {preview}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:20]:
            preview = refusal["claim_text"][:120].replace("\n", " ")
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Packet: {refusal['manual_after_snapshot_packet_id']}",
                    f"  - Text Preview: {preview}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    return "\n".join(
        [
            "# Manual AFTER Snapshot Claim Extraction v2",
            "",
            "This lane extracts conservative manual-review claim candidates from "
            "manual AFTER snapshot evidence packets. It does not invent claims, "
            "normalize claims, create embeddings, create contradictions, fetch "
            "URLs, read refused snapshots, create proof chains, create final "
            "reports, mark production readiness, or approve evidence.",
            "",
            "## Summary",
            f"- manual_after_snapshot_claim_status: {status}",
            f"- mode: {mode}",
            f"- manual_after_snapshot_packet_count: {packet_count}",
            f"- manual_after_snapshot_claim_count: {len(claims)}",
            f"- refusal_count: {len(refusals)}",
            f"- manual_after_snapshot_claim_root: {root}",
            "",
            "## First Manual AFTER Snapshot Claims",
            *claim_lines,
            "",
            "## First Refusals",
            *refusal_lines,
            "",
            "## Guardrails",
            "- Claims Invented: 0",
            "- Claims Normalized: 0",
            "- Embeddings Created: 0",
            "- Contradictions Created: 0",
            "- Proof Chains Created: 0",
            "- Final Reports Created: 0",
            "- URLs Fetched: 0",
            "- Production Ready: False",
            "- Approved Evidence: 0",
            "",
        ]
    )


def build_manual_after_snapshot_claim_extraction(
    mode: str = "dry-run",
    packets_path: Path = DEFAULT_PACKETS,
    packet_summary_path: Path = DEFAULT_PACKET_SUMMARY,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "extract-claims"):
        raise ValueError("mode must be 'dry-run' or 'extract-claims'.")

    packets = _load_packets(packets_path)
    _validate_upstream_summary(packet_summary_path, len(packets))
    schema = _schema_payload()
    schema_hash = _hash_json(schema)

    claims: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    valid_packet_ids: List[str] = []
    seen_packet_ids = set()
    validated_packet_count = 0

    if mode == "dry-run":
        for packet in packets:
            _validate_packet(packet)
            packet_id = packet["manual_after_snapshot_packet_id"]
            if packet_id in seen_packet_ids:
                raise ManualAfterSnapshotClaimRefusal(
                    "REFUSED_DUPLICATE_PACKET_ID",
                    f"Duplicate manual_after_snapshot_packet_id: {packet_id}.",
                )
            seen_packet_ids.add(packet_id)
            valid_packet_ids.append(packet_id)
            validated_packet_count += 1
    else:
        for packet in packets:
            packet_id = str(packet.get("manual_after_snapshot_packet_id") or "")
            if packet_id in seen_packet_ids:
                refusal = _make_refusal(
                    packet,
                    str(packet.get("evidence_text") or ""),
                    "REFUSED_DUPLICATE_PACKET_ID",
                    f"Duplicate manual_after_snapshot_packet_id: {packet_id}.",
                )
                validate_refusal(refusal)
                refusals.append(refusal)
                continue
            seen_packet_ids.add(packet_id)
            valid_packet_ids.append(packet_id)
            packet_claims, packet_refusals = _claims_or_refusals(packet, len(claims) + 1)
            claims.extend(packet_claims)
            refusals.extend(packet_refusals)
            if packet_claims or any(
                refusal["refusal_code"] not in (
                    "REFUSED_MALFORMED_PACKET",
                    "REFUSED_NON_AFTER_PACKET",
                    "REFUSED_NON_MANUAL_AFTER_SOURCE",
                    "REFUSED_HASH_OR_ROOT_MISMATCH",
                )
                for refusal in packet_refusals
            ):
                validated_packet_count += 1

    for claim in claims:
        validate_claim(claim, valid_packet_ids)
    for refusal in refusals:
        validate_refusal(refusal)

    status = _status_for(mode, len(claims), len(refusals))
    summary = {
        "manual_after_snapshot_claim_status": status,
        "mode": mode,
        "manual_after_snapshot_packet_count": len(packets),
        "validated_packet_count": validated_packet_count,
        "manual_after_snapshot_claim_count": len(claims),
        "refusal_count": len(refusals),
        "after_claim_count": sum(1 for claim in claims if claim["time_direction"] == TIME_DIRECTION),
        "claim_type_counts": {
            claim_type: sum(1 for claim in claims if claim["claim_type"] == claim_type)
            for claim_type in CLAIM_TYPES
        },
        "packet_ids": [
            str(packet.get("manual_after_snapshot_packet_id") or "") for packet in packets
        ],
        "claim_roots": [claim["claim_root"] for claim in claims],
        "refusal_roots": [refusal["refusal_root"] for refusal in refusals],
        "refusal_code_counts": {
            code: sum(1 for refusal in refusals if refusal["refusal_code"] == code)
            for code in REFUSAL_CODES
        },
        "lineage_preserved": True,
        "hashes_preserved": True,
        "roots_preserved": True,
        "packet_text_exact_copy": True,
        "manual_after_snapshot_claim_schema_hash": schema_hash,
        "manual_after_snapshot_claim_report_hash": "",
        "manual_after_snapshot_claim_root": "",
        "claims_invented": 0,
        "claims_normalized": 0,
        "embeddings_created": 0,
        "contradictions_created": 0,
        "proof_chains_created": 0,
        "final_reports_created": 0,
        "urls_fetched": 0,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "no_generated_outputs_committed": True,
    }
    summary["manual_after_snapshot_claim_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(packets),
        claims,
        refusals,
        summary["manual_after_snapshot_claim_root"],
    )
    summary["manual_after_snapshot_claim_report_hash"] = _sha256_text(report)
    summary["manual_after_snapshot_claim_root"] = _hash_json(_summary_root_material(summary))
    report = _build_report(
        status,
        mode,
        len(packets),
        claims,
        refusals,
        summary["manual_after_snapshot_claim_root"],
    )

    for counter_name in (
        "claims_invented",
        "claims_normalized",
        "embeddings_created",
        "contradictions_created",
        "proof_chains_created",
        "final_reports_created",
        "urls_fetched",
    ):
        if summary[counter_name] != 0:
            raise ValueError(f"{counter_name} must remain 0.")
    if not _closed_flags(summary):
        raise ValueError("Manual AFTER snapshot claim extraction guardrails must remain closed.")

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / SUMMARY_OUTPUT.name, summary)
    _write_json(
        output_dir / CLAIMS_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "manual_after_snapshot_claims": claims,
        },
    )
    _write_json(
        output_dir / REFUSALS_OUTPUT.name,
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "manual_after_snapshot_claim_refusals": refusals,
        },
    )
    _write_text(output_dir / REPORT_OUTPUT.name, report)

    return {
        "summary": summary,
        "manual_after_snapshot_claims": claims,
        "manual_after_snapshot_claim_refusals": refusals,
        "schema": schema,
        "report": report,
    }


__all__ = ["build_manual_after_snapshot_claim_extraction"]
