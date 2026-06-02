#!/usr/bin/env python3
"""
Manual Review Endpoint Promotion Engine v2.

Promotes registry strategy candidates only after deterministic public
reachability and metadata checks. This lane does not discover new endpoints,
scrape quotes, extract transcripts, create claims, create contradictions, or
modify downstream engines.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse
import hashlib
import json
import urllib.error
import urllib.request


DEFAULT_STRATEGY_CANDIDATES = Path(
    "outputs/registry_source_discovery_strategy_upgrade/strategy_candidates.json"
)
DEFAULT_STRATEGY_SUMMARY = Path(
    "outputs/registry_source_discovery_strategy_upgrade/strategy_upgrade_summary.json"
)
DEFAULT_STRATEGY_REFUSALS = Path(
    "outputs/registry_source_discovery_strategy_upgrade/strategy_refusals.json"
)
DEFAULT_REGISTRY_INPUT = Path("inputs/source_registry/duma_boko_source_registry.json")

DEFAULT_OUTPUT_DIR = Path("outputs/manual_review_endpoint_promotion_engine")
STATUS_OUTPUT = DEFAULT_OUTPUT_DIR / "endpoint_promotion_status.json"
SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "endpoint_promotion_summary.json"
PROMOTED_OUTPUT = DEFAULT_OUTPUT_DIR / "promoted_registry_endpoints.json"
REFUSALS_OUTPUT = DEFAULT_OUTPUT_DIR / "endpoint_promotion_refusals.json"
REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "endpoint_promotion_report.md"
SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIR / "endpoint_promotion_schema.json"

SCHEMA_VERSION = "manual_review_endpoint_promotion_engine_v2"
UPSTREAM_STRATEGY_SCHEMA_VERSION = "registry_source_discovery_strategy_upgrade_v2"
UPSTREAM_REGISTRY_SCHEMA_VERSION = "canonical_source_registry_engine_v2"

DRY_RUN_STATUS = "ENDPOINT_PROMOTION_DRY_RUN_REVIEW_REQUIRED"
CANDIDATE_STATUS = "ENDPOINT_PROMOTION_CANDIDATE"
PARTIAL_STATUS = "ENDPOINT_PROMOTION_PARTIAL"
REFUSED_STATUS = "ENDPOINT_PROMOTION_REFUSED"

UNSPECIFIED = "UNSPECIFIED"

SOURCE_CATEGORIES = (
    "official_party",
    "official_government",
    "parliament_record",
    "youtube_channel",
    "facebook_page",
    "x_twitter_account",
    "news_publisher",
    "radio_tv_broadcaster",
    "public_archive",
    "manual_review_source",
)

SUPPORTED_PLATFORMS = (
    "party_public_communications",
    "government_public_communications",
    "parliament_record_search",
    "youtube",
    "facebook",
    "x_twitter",
    "news_archive_search",
    "broadcast_archive_search",
    "public_archive_search",
    "manual_review",
)

STRATEGY_CANDIDATE_FIELDS = (
    "strategy_candidate_id",
    "registry_target_id",
    "source_name",
    "source_category",
    "platform",
    "strategy_name",
    "query",
    "candidate_url",
    "http_status",
    "content_type",
    "verification_status",
    "manual_review_required",
    "reasoning_summary",
    "metadata_hash",
    "strategy_candidate_root",
)

PROMOTED_ENDPOINT_FIELDS = (
    "promoted_endpoint_id",
    "strategy_candidate_id",
    "registry_target_id",
    "source_name",
    "source_category",
    "platform",
    "base_url",
    "resolved_url",
    "http_status",
    "content_type",
    "redirect_chain",
    "verification_status",
    "promotion_method",
    "manual_review_required",
    "reasoning_summary",
    "metadata_hash",
    "promoted_endpoint_root",
)

REFUSAL_FIELDS = (
    "refusal_id",
    "strategy_candidate_id",
    "registry_target_id",
    "candidate_url",
    "refusal_code",
    "refusal_reason",
    "http_status",
    "content_type",
    "manual_review_required",
    "refusal_root",
)

REGISTRY_SOURCE_FIELDS = (
    "registry_source_id",
    "source_name",
    "source_category",
    "platform",
    "base_url",
    "search_url_template",
    "speaker_focus",
    "geographic_context",
    "trust_tier",
    "expected_source_types",
    "manual_review_required",
    "notes",
)

APPLIED_REGISTRY_OPTIONAL_FIELDS = (
    "resolved_url",
    "verification_status",
    "source_origin",
    "verified_endpoints",
)

VERIFICATION_STATUSES = (
    "PROMOTED_VERIFIED_PUBLIC_ENDPOINT",
    "PROMOTED_SEARCH_ENDPOINT_REVIEW_REQUIRED",
    "DISCOVERED_REQUIRES_MANUAL_REVIEW",
    "REFUSED_UNREACHABLE",
    "REFUSED_LOGIN_REQUIRED",
    "REFUSED_METADATA_UNVERIFIED",
    "REFUSED_GENERIC_SEARCH_RESULT",
    "REFUSED_UNSUPPORTED_PLATFORM",
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


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def _require_nonempty_string(data: Dict[str, Any], field_name: str, object_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{object_name}.{field_name} must be a non-empty string")


def _is_nonzero_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"0"}


def _closed_flags(data: Dict[str, Any]) -> bool:
    return (
        data.get("production_ready") is False
        and data.get("approved_evidence") == 0
        and data.get("public_ready") is False
        and data.get("institutional_ready") is False
    )


def _is_public_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _registry_source_fields_are_supported(source: Dict[str, Any]) -> bool:
    required_fields = set(REGISTRY_SOURCE_FIELDS)
    optional_fields = set(APPLIED_REGISTRY_OPTIONAL_FIELDS)
    source_fields = set(source.keys())
    return required_fields <= source_fields and not source_fields - required_fields - optional_fields


def _base_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return UNSPECIFIED
    return f"{parsed.scheme}://{parsed.netloc}/"


def _is_generic_search_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    query = parsed.query.lower()
    if host.endswith("google.com") and path.startswith("/search"):
        return True
    if host.endswith("bing.com") and path.startswith("/search"):
        return True
    if host.endswith("duckduckgo.com") and (path.startswith("/html") or "q=" in query):
        return True
    if host.endswith("youtube.com") and path.startswith("/results"):
        return True
    if host.endswith("facebook.com") and path.startswith("/search"):
        return True
    if host.endswith("twitter.com") and path.startswith("/search"):
        return True
    if host.endswith("x.com") and path.startswith("/search"):
        return True
    return False


def _is_login_required(url: str, page_text: str) -> bool:
    lowered_url = url.lower()
    lowered_text = page_text.lower()
    if any(marker in lowered_url for marker in ("/login", "login?", "/i/flow/login")):
        return True
    return any(
        marker in lowered_text
        for marker in (
            "login required",
            "sign in to continue",
            "log in to continue",
            "create an account",
            "you must log in",
        )
    )


def _schema() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "manual_review_endpoint_promotion_only": True,
        "upstream_schema_version": UPSTREAM_STRATEGY_SCHEMA_VERSION,
        "promoted_endpoint_fields": list(PROMOTED_ENDPOINT_FIELDS),
        "refusal_fields": list(REFUSAL_FIELDS),
        "source_categories": list(SOURCE_CATEGORIES),
        "supported_platforms": list(SUPPORTED_PLATFORMS),
        "verification_statuses": list(VERIFICATION_STATUSES),
        "modes": ["dry-run", "verify-endpoints"],
        "promotion_rules": {
            "verified_endpoint_requires": [
                "candidate_url is non-empty public HTTP(S)",
                "http_status is 200-399",
                "not login required",
                "not a generic search-result page",
                "content_type is non-empty",
                "metadata_hash is non-empty",
            ],
            "generic_search_pages": (
                "Reachable search pages remain PROMOTED_SEARCH_ENDPOINT_REVIEW_REQUIRED "
                "and do not count as verified endpoints."
            ),
        },
        "prohibited_outputs": {
            "quotes_created": 0,
            "timestamps_created": 0,
            "transcripts_created": 0,
            "claims_created": 0,
            "contradictions_created": 0,
        },
        "closed_governance_flags": {
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        },
    }


def validate_schema(schema: Dict[str, Any]) -> None:
    if schema.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("endpoint_promotion_schema schema_version changed")
    if schema.get("promoted_endpoint_fields") != list(PROMOTED_ENDPOINT_FIELDS):
        raise ValueError("promoted endpoint fields changed")
    if schema.get("refusal_fields") != list(REFUSAL_FIELDS):
        raise ValueError("endpoint promotion refusal fields changed")


def _metadata_material(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        field: record[field]
        for field in PROMOTED_ENDPOINT_FIELDS
        if field not in ("metadata_hash", "promoted_endpoint_root")
    }


def _endpoint_root_material(record: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(record)
    material.pop("promoted_endpoint_root", None)
    return material


def _refusal_root_material(refusal: Dict[str, Any]) -> Dict[str, Any]:
    material = dict(refusal)
    material.pop("refusal_root", None)
    return material


def _make_endpoint_record(
    sequence_number: int,
    candidate: Dict[str, Any],
    base_url: str,
    resolved_url: str,
    http_status: int,
    content_type: str,
    redirect_chain: List[str],
    verification_status: str,
    promotion_method: str,
    reasoning_summary: str,
) -> Dict[str, Any]:
    record = {
        "promoted_endpoint_id": f"PROMOTED_ENDPOINT_{sequence_number:03d}",
        "strategy_candidate_id": candidate["strategy_candidate_id"],
        "registry_target_id": candidate["registry_target_id"],
        "source_name": candidate["source_name"],
        "source_category": candidate["source_category"],
        "platform": candidate["platform"],
        "base_url": base_url,
        "resolved_url": resolved_url,
        "http_status": int(http_status),
        "content_type": content_type or UNSPECIFIED,
        "redirect_chain": redirect_chain,
        "verification_status": verification_status,
        "promotion_method": promotion_method,
        "manual_review_required": True,
        "reasoning_summary": reasoning_summary,
        "metadata_hash": "",
        "promoted_endpoint_root": "",
    }
    record["metadata_hash"] = _hash_json(_metadata_material(record))
    record["promoted_endpoint_root"] = _hash_json(_endpoint_root_material(record))
    return record


def _make_refusal(
    sequence_number: int,
    candidate: Dict[str, Any],
    refusal_code: str,
    refusal_reason: str,
    http_status: int = 0,
    content_type: str = UNSPECIFIED,
) -> Dict[str, Any]:
    refusal = {
        "refusal_id": f"ENDPOINT_PROMOTION_REFUSAL_{sequence_number:03d}",
        "strategy_candidate_id": candidate["strategy_candidate_id"],
        "registry_target_id": candidate["registry_target_id"],
        "candidate_url": candidate["candidate_url"] or UNSPECIFIED,
        "refusal_code": refusal_code,
        "refusal_reason": refusal_reason,
        "http_status": int(http_status),
        "content_type": content_type or UNSPECIFIED,
        "manual_review_required": True,
        "refusal_root": "",
    }
    refusal["refusal_root"] = _hash_json(_refusal_root_material(refusal))
    return refusal


def validate_strategy_candidate(candidate: Dict[str, Any]) -> None:
    if set(candidate.keys()) != set(STRATEGY_CANDIDATE_FIELDS):
        raise ValueError("Strategy candidate fields changed unexpectedly")
    for field_name in (
        "strategy_candidate_id",
        "registry_target_id",
        "source_name",
        "source_category",
        "platform",
        "strategy_name",
        "query",
        "candidate_url",
        "content_type",
        "verification_status",
        "reasoning_summary",
        "metadata_hash",
        "strategy_candidate_root",
    ):
        _require_nonempty_string(candidate, field_name, "StrategyCandidate")
    if candidate["source_category"] not in SOURCE_CATEGORIES:
        raise ValueError(f"Unsupported source_category: {candidate['source_category']}")
    if candidate["platform"] not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported platform: {candidate['platform']}")
    if candidate["manual_review_required"] is not True:
        raise ValueError("StrategyCandidate.manual_review_required must remain true")
    if not isinstance(candidate["http_status"], int):
        raise ValueError("StrategyCandidate.http_status must be an integer")


def validate_promoted_endpoint(record: Dict[str, Any]) -> None:
    if set(record.keys()) != set(PROMOTED_ENDPOINT_FIELDS):
        raise ValueError("Promoted endpoint fields changed unexpectedly")
    for field_name in (
        "promoted_endpoint_id",
        "strategy_candidate_id",
        "registry_target_id",
        "source_name",
        "source_category",
        "platform",
        "base_url",
        "resolved_url",
        "content_type",
        "verification_status",
        "promotion_method",
        "reasoning_summary",
        "metadata_hash",
        "promoted_endpoint_root",
    ):
        _require_nonempty_string(record, field_name, "PromotedEndpoint")
    if record["source_category"] not in SOURCE_CATEGORIES:
        raise ValueError(f"Unsupported source_category: {record['source_category']}")
    if record["platform"] not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported platform: {record['platform']}")
    if record["verification_status"] not in VERIFICATION_STATUSES:
        raise ValueError(f"Unsupported verification_status: {record['verification_status']}")
    if record["verification_status"].startswith("REFUSED_"):
        raise ValueError("Promoted endpoint records must not carry refusal statuses")
    if record["manual_review_required"] is not True:
        raise ValueError("PromotedEndpoint.manual_review_required must remain true")
    if not isinstance(record["http_status"], int):
        raise ValueError("PromotedEndpoint.http_status must be an integer")
    if not isinstance(record["redirect_chain"], list):
        raise ValueError("PromotedEndpoint.redirect_chain must be a list")
    if record["verification_status"] == "PROMOTED_VERIFIED_PUBLIC_ENDPOINT":
        if not _is_public_url(record["resolved_url"]):
            raise ValueError("Verified promoted endpoint resolved_url must be public")
        if record["http_status"] < 200 or record["http_status"] >= 400:
            raise ValueError("Verified promoted endpoint http_status must be 200-399")
        if _is_generic_search_url(record["resolved_url"]) or _is_generic_search_url(record["base_url"]):
            raise ValueError("Generic search result pages must not be verified endpoints")
        if not _is_nonzero_hash(record["metadata_hash"]):
            raise ValueError("Verified promoted endpoint metadata_hash must be non-empty")
    if record["verification_status"] == "PROMOTED_SEARCH_ENDPOINT_REVIEW_REQUIRED":
        if record["http_status"] < 200 or record["http_status"] >= 400:
            raise ValueError("Reachable search endpoint review record must have HTTP 200-399")
        if not (
            _is_generic_search_url(record["resolved_url"])
            or _is_generic_search_url(record["base_url"])
            or _is_generic_search_url(record["redirect_chain"][0])
        ):
            raise ValueError("Search endpoint review record must refer to a generic search URL")
    if record["metadata_hash"] != _hash_json(_metadata_material(record)):
        raise ValueError(f"metadata_hash mismatch for {record['promoted_endpoint_id']}")
    if record["promoted_endpoint_root"] != _hash_json(_endpoint_root_material(record)):
        raise ValueError(f"root mismatch for {record['promoted_endpoint_id']}")


def validate_refusal(refusal: Dict[str, Any]) -> None:
    if set(refusal.keys()) != set(REFUSAL_FIELDS):
        raise ValueError("Endpoint promotion refusal fields changed unexpectedly")
    for field_name in (
        "refusal_id",
        "strategy_candidate_id",
        "registry_target_id",
        "candidate_url",
        "refusal_code",
        "refusal_reason",
        "content_type",
        "refusal_root",
    ):
        _require_nonempty_string(refusal, field_name, "EndpointPromotionRefusal")
    if refusal["refusal_code"] not in VERIFICATION_STATUSES:
        raise ValueError(f"Unsupported refusal_code: {refusal['refusal_code']}")
    if not refusal["refusal_code"].startswith("REFUSED_"):
        raise ValueError("Endpoint promotion refusal code must be a REFUSED_* status")
    if refusal["manual_review_required"] is not True:
        raise ValueError("EndpointPromotionRefusal.manual_review_required must be true")
    if not isinstance(refusal["http_status"], int):
        raise ValueError("EndpointPromotionRefusal.http_status must be an integer")
    if refusal["refusal_root"] != _hash_json(_refusal_root_material(refusal)):
        raise ValueError(f"refusal_root mismatch for {refusal['refusal_id']}")


def _validate_registry_source(source: Dict[str, Any]) -> None:
    if not _registry_source_fields_are_supported(source):
        raise ValueError("Registry source fields changed unexpectedly")
    for field_name in (
        "registry_source_id",
        "source_name",
        "source_category",
        "platform",
        "base_url",
        "search_url_template",
        "speaker_focus",
        "geographic_context",
        "notes",
    ):
        _require_nonempty_string(source, field_name, "RegistrySource")
    if source["source_category"] not in SOURCE_CATEGORIES:
        raise ValueError(f"Unsupported source_category: {source['source_category']}")
    if source["platform"] not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported platform: {source['platform']}")
    if source["manual_review_required"] is not True:
        raise ValueError("RegistrySource.manual_review_required must remain true")


def _validate_upstream(
    strategy_candidates_payload: Dict[str, Any],
    strategy_summary: Dict[str, Any],
    strategy_refusals_payload: Dict[str, Any],
    registry_input: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not strategy_candidates_payload:
        raise ValueError("strategy candidates output is missing")
    if not strategy_summary:
        raise ValueError("strategy upgrade summary output is missing")
    if not strategy_refusals_payload:
        raise ValueError("strategy refusals output is missing")
    if not registry_input:
        raise ValueError("source registry input is missing")
    if registry_input.get("registry_version") != UPSTREAM_REGISTRY_SCHEMA_VERSION:
        raise ValueError("source registry input version is invalid")
    registry_sources = registry_input.get("registry_sources")
    if not isinstance(registry_sources, list) or len(registry_sources) != 20:
        raise ValueError("source registry input must contain 20 source families")
    for source in registry_sources:
        _validate_registry_source(source)
    if not _closed_flags(strategy_summary):
        raise ValueError("strategy upgrade guardrails must remain closed")
    for counter_name in (
        "quotes_created",
        "timestamps_created",
        "transcripts_created",
        "claims_created",
        "contradictions_created",
    ):
        if strategy_summary.get(counter_name) != 0:
            raise ValueError(f"strategy upgrade {counter_name} must be 0")
    if strategy_summary.get("strategy_upgrade_status") not in (
        "REGISTRY_SOURCE_DISCOVERY_STRATEGY_DEMO_CANDIDATE",
        "REGISTRY_SOURCE_DISCOVERY_STRATEGY_CANDIDATE",
        "REGISTRY_SOURCE_DISCOVERY_STRATEGY_PARTIAL",
        "REGISTRY_SOURCE_DISCOVERY_STRATEGY_REFUSED",
    ):
        raise ValueError("strategy upgrade status is invalid")
    candidates = strategy_candidates_payload.get("strategy_candidates")
    if not isinstance(candidates, list) or len(candidates) != 64:
        raise ValueError("strategy_candidates must contain exactly 64 strategy candidates")
    if strategy_summary.get("strategy_candidate_count") != len(candidates):
        raise ValueError("strategy candidate count does not match summary")
    strategy_refusals = strategy_refusals_payload.get("strategy_refusals")
    if not isinstance(strategy_refusals, list):
        raise ValueError("strategy_refusals must be a list")
    for candidate in candidates:
        validate_strategy_candidate(candidate)
    registry_ids = {source["registry_source_id"] for source in registry_sources}
    for candidate in candidates:
        if candidate["registry_target_id"] not in registry_ids:
            raise ValueError(f"strategy candidate target missing from registry: {candidate['registry_target_id']}")
    return candidates


def _request_url(url: str, method: str) -> Tuple[int, str, str, str]:
    request = urllib.request.Request(
        url,
        method=method,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; ManualReviewEndpointPromotion/2.0; "
                "endpoint-verification-only)"
            )
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            content_type = response.headers.get("content-type", "")
            body = ""
            if method == "GET" and ("text/html" in content_type or "application/xhtml" in content_type):
                body = response.read(500000).decode("utf-8", errors="replace")
            return int(response.status), response.geturl(), content_type, body
    except urllib.error.HTTPError as exc:
        content_type = exc.headers.get("content-type", "") if exc.headers else ""
        return int(exc.code), exc.geturl(), content_type, ""


def _verify_candidate(
    endpoint_sequence_number: int,
    refusal_sequence_number: int,
    candidate: Dict[str, Any],
    mode: str,
) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
    candidate_url = candidate["candidate_url"].strip()
    if candidate["platform"] not in SUPPORTED_PLATFORMS:
        return None, _make_refusal(
            refusal_sequence_number,
            candidate,
            "REFUSED_UNSUPPORTED_PLATFORM",
            "Strategy candidate platform is not supported by endpoint promotion.",
        )
    if not _is_public_url(candidate_url):
        return None, _make_refusal(
            refusal_sequence_number,
            candidate,
            "REFUSED_METADATA_UNVERIFIED",
            "Strategy candidate URL is not public HTTP(S).",
        )
    base_url = _base_url(candidate_url)
    if mode == "dry-run":
        return _make_endpoint_record(
            endpoint_sequence_number,
            candidate,
            base_url,
            candidate_url,
            0,
            UNSPECIFIED,
            [candidate_url],
            "DISCOVERED_REQUIRES_MANUAL_REVIEW",
            "dry_run_manual_review_preservation",
            "Dry-run only; candidate is preserved for manual review and not promoted.",
        ), None

    last_error = ""
    last_status = 0
    last_content_type = UNSPECIFIED
    for method in ("HEAD", "GET"):
        try:
            status, resolved_url, content_type, body = _request_url(candidate_url, method)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            last_error = str(exc)
            continue
        last_status = status
        last_content_type = content_type or UNSPECIFIED
        if status < 200 or status >= 400:
            last_error = f"HTTP status {status} is not an accepted public success status."
            continue
        if not _is_public_url(resolved_url):
            return None, _make_refusal(
                refusal_sequence_number,
                candidate,
                "REFUSED_METADATA_UNVERIFIED",
                "Resolved URL is not public HTTP(S).",
                status,
                last_content_type,
            )
        if not content_type:
            return None, _make_refusal(
                refusal_sequence_number,
                candidate,
                "REFUSED_METADATA_UNVERIFIED",
                "Reachable endpoint did not provide a content-type header.",
                status,
                UNSPECIFIED,
            )
        if _is_login_required(resolved_url, body):
            return None, _make_refusal(
                refusal_sequence_number,
                candidate,
                "REFUSED_LOGIN_REQUIRED",
                "Endpoint appears to require login.",
                status,
                content_type,
            )
        redirect_chain = [candidate_url]
        if resolved_url != candidate_url:
            redirect_chain.append(resolved_url)
        if _is_generic_search_url(candidate_url) or _is_generic_search_url(resolved_url):
            return _make_endpoint_record(
                endpoint_sequence_number,
                candidate,
                base_url,
                resolved_url,
                status,
                content_type,
                redirect_chain,
                "PROMOTED_SEARCH_ENDPOINT_REVIEW_REQUIRED",
                f"{method.lower()}_reachable_search_endpoint_review",
                "Reachable generic search endpoint preserved for review; not promoted as a verified source endpoint.",
            ), None
        return _make_endpoint_record(
            endpoint_sequence_number,
            candidate,
            base_url,
            resolved_url,
            status,
            content_type,
            redirect_chain,
            "PROMOTED_VERIFIED_PUBLIC_ENDPOINT",
            f"{method.lower()}_public_reachability_check",
            "Candidate URL passed deterministic public reachability and metadata checks.",
        ), None

    refusal_code = "REFUSED_GENERIC_SEARCH_RESULT" if _is_generic_search_url(candidate_url) else "REFUSED_UNREACHABLE"
    refusal_reason = "Generic search result endpoint was not reachable." if refusal_code == "REFUSED_GENERIC_SEARCH_RESULT" else (
        f"Unable to verify endpoint reachability: {last_error or 'no response'}"
    )
    return None, _make_refusal(
        refusal_sequence_number,
        candidate,
        refusal_code,
        refusal_reason,
        last_status,
        last_content_type,
    )


def _status_for(mode: str, promoted_count: int, search_review_count: int, refusal_count: int) -> str:
    if mode == "dry-run":
        return DRY_RUN_STATUS
    review_count = promoted_count + search_review_count
    if promoted_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    if review_count > 0 and refusal_count > 0:
        return PARTIAL_STATUS
    if review_count > 0 and refusal_count == 0:
        return CANDIDATE_STATUS
    return REFUSED_STATUS


def _build_report(
    status: str,
    mode: str,
    endpoint_records: List[Dict[str, Any]],
    refusals: List[Dict[str, Any]],
    root: str,
) -> str:
    promoted_lines = ["- None"]
    promoted_verified = [
        record
        for record in endpoint_records
        if record["verification_status"] == "PROMOTED_VERIFIED_PUBLIC_ENDPOINT"
    ]
    if promoted_verified:
        promoted_lines = []
        for record in promoted_verified[:40]:
            promoted_lines.extend(
                [
                    f"- {record['promoted_endpoint_id']}",
                    f"  - Source: {record['source_name']}",
                    f"  - Resolved URL: {record['resolved_url']}",
                    f"  - HTTP Status: {record['http_status']}",
                ]
            )
    refusal_lines = ["- None"]
    if refusals:
        refusal_lines = []
        for refusal in refusals[:40]:
            refusal_lines.extend(
                [
                    f"- {refusal['refusal_id']}: {refusal['refusal_code']}",
                    f"  - Candidate URL: {refusal['candidate_url']}",
                    f"  - Reason: {refusal['refusal_reason']}",
                ]
            )
    lines = [
        "# Manual Review Endpoint Promotion Engine v2",
        "",
        "This lane promotes candidate endpoints only after deterministic public "
        "reachability and metadata checks. It does not create quotes, timestamps, "
        "transcripts, claims, contradictions, proof chains, or downstream reports.",
        "",
        "## Summary",
        f"- endpoint_promotion_status: {status}",
        f"- mode: {mode}",
        f"- strategy_candidate_count: {len(endpoint_records) + len(refusals)}",
        f"- promoted_endpoint_count: {sum(1 for record in endpoint_records if record['verification_status'] == 'PROMOTED_VERIFIED_PUBLIC_ENDPOINT')}",
        f"- search_endpoint_review_count: {sum(1 for record in endpoint_records if record['verification_status'] == 'PROMOTED_SEARCH_ENDPOINT_REVIEW_REQUIRED')}",
        f"- manual_review_candidate_count: {sum(1 for record in endpoint_records if record['verification_status'] == 'DISCOVERED_REQUIRES_MANUAL_REVIEW')}",
        f"- refusal_count: {len(refusals)}",
        f"- endpoint_promotion_root: {root}",
        "",
        "## Promoted Verified Endpoints",
        *promoted_lines,
        "",
        "## Refusals",
        *refusal_lines,
        "",
        "## Guardrails",
        "- Quotes Created: 0",
        "- Timestamps Created: 0",
        "- Transcripts Created: 0",
        "- Claims Created: 0",
        "- Contradictions Created: 0",
        "- Production Ready: False",
        "- Approved Evidence: 0",
        "- Public Ready: False",
        "- Institutional Ready: False",
        "",
    ]
    return "\n".join(lines)


def build_manual_review_endpoint_promotion_engine(
    mode: str = "dry-run",
    strategy_candidates_path: Path = DEFAULT_STRATEGY_CANDIDATES,
    strategy_summary_path: Path = DEFAULT_STRATEGY_SUMMARY,
    strategy_refusals_path: Path = DEFAULT_STRATEGY_REFUSALS,
    registry_input_path: Path = DEFAULT_REGISTRY_INPUT,
) -> Dict[str, Any]:
    if mode not in ("dry-run", "verify-endpoints"):
        raise ValueError("mode must be dry-run or verify-endpoints")
    strategy_candidates_payload = _load_json(strategy_candidates_path)
    strategy_summary = _load_json(strategy_summary_path)
    strategy_refusals_payload = _load_json(strategy_refusals_path)
    registry_input = _load_json(registry_input_path)
    candidates = _validate_upstream(
        strategy_candidates_payload,
        strategy_summary,
        strategy_refusals_payload,
        registry_input,
    )
    schema = _schema()
    validate_schema(schema)

    endpoint_records: List[Dict[str, Any]] = []
    refusals: List[Dict[str, Any]] = []
    for candidate in candidates:
        endpoint_record, refusal = _verify_candidate(
            len(endpoint_records) + 1,
            len(refusals) + 1,
            candidate,
            mode,
        )
        if endpoint_record is not None:
            validate_promoted_endpoint(endpoint_record)
            endpoint_records.append(endpoint_record)
        if refusal is not None:
            validate_refusal(refusal)
            refusals.append(refusal)

    promoted_roots = [
        record["promoted_endpoint_root"]
        for record in endpoint_records
        if record["verification_status"] == "PROMOTED_VERIFIED_PUBLIC_ENDPOINT"
    ]
    manual_review_roots = [
        record["promoted_endpoint_root"]
        for record in endpoint_records
        if record["verification_status"] in (
            "DISCOVERED_REQUIRES_MANUAL_REVIEW",
            "PROMOTED_SEARCH_ENDPOINT_REVIEW_REQUIRED",
        )
    ]
    refusal_roots = [refusal["refusal_root"] for refusal in refusals]
    root = _hash_json(
        {
            "promoted_endpoint_roots": sorted(promoted_roots),
            "manual_review_candidate_roots": sorted(manual_review_roots),
            "refusal_roots": sorted(refusal_roots),
            "quotes_created": 0,
            "timestamps_created": 0,
            "transcripts_created": 0,
            "claims_created": 0,
            "contradictions_created": 0,
            "production_ready": False,
            "approved_evidence": 0,
            "public_ready": False,
            "institutional_ready": False,
        }
    )
    promoted_endpoint_count = len(promoted_roots)
    verified_public_endpoint_count = promoted_endpoint_count
    search_endpoint_review_count = sum(
        1
        for record in endpoint_records
        if record["verification_status"] == "PROMOTED_SEARCH_ENDPOINT_REVIEW_REQUIRED"
    )
    manual_review_candidate_count = sum(
        1
        for record in endpoint_records
        if record["verification_status"] == "DISCOVERED_REQUIRES_MANUAL_REVIEW"
    )
    status = _status_for(mode, promoted_endpoint_count, search_endpoint_review_count, len(refusals))
    report = _build_report(status, mode, endpoint_records, refusals, root)
    summary = {
        "endpoint_promotion_status": status,
        "mode": mode,
        "strategy_candidate_count": len(candidates),
        "promoted_endpoint_count": promoted_endpoint_count,
        "verified_public_endpoint_count": verified_public_endpoint_count,
        "search_endpoint_review_count": search_endpoint_review_count,
        "manual_review_candidate_count": manual_review_candidate_count,
        "refusal_count": len(refusals),
        "quotes_created": 0,
        "timestamps_created": 0,
        "transcripts_created": 0,
        "claims_created": 0,
        "contradictions_created": 0,
        "evidence_approved_count": 0,
        "promoted_endpoint_roots": promoted_roots,
        "manual_review_candidate_roots": manual_review_roots,
        "refusal_roots": refusal_roots,
        "endpoint_promotion_schema_hash": _hash_json(schema),
        "endpoint_promotion_report_hash": _sha256_text(report),
        "endpoint_promotion_root": root,
        "production_ready": False,
        "approved_evidence": 0,
        "public_ready": False,
        "institutional_ready": False,
        "deterministic_json": True,
        "sha256_roots": True,
        "downstream_engines_untouched": True,
        "no_generated_outputs_committed": True,
    }
    if mode == "dry-run":
        expected = {
            "endpoint_promotion_status": DRY_RUN_STATUS,
            "strategy_candidate_count": 64,
            "promoted_endpoint_count": 0,
            "verified_public_endpoint_count": 0,
            "search_endpoint_review_count": 0,
            "manual_review_candidate_count": 64,
            "refusal_count": 0,
        }
        for key, expected_value in expected.items():
            if summary.get(key) != expected_value:
                raise ValueError(f"dry-run {key} must be {expected_value}")
    if not _closed_flags(summary):
        raise ValueError("Endpoint promotion guardrails must remain closed")

    status_payload = {
        "records": [
            {
                "endpoint_promotion_status": status,
                "strategy_candidate_count": len(candidates),
                "promoted_endpoint_count": promoted_endpoint_count,
                "verified_public_endpoint_count": verified_public_endpoint_count,
                "search_endpoint_review_count": search_endpoint_review_count,
                "manual_review_candidate_count": manual_review_candidate_count,
                "refusal_count": len(refusals),
                "endpoint_promotion_root": root,
                "production_ready": False,
                "approved_evidence": 0,
                "public_ready": False,
                "institutional_ready": False,
            }
        ]
    }
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(STATUS_OUTPUT, status_payload)
    _write_json(SUMMARY_OUTPUT, summary)
    _write_json(PROMOTED_OUTPUT, {"promoted_registry_endpoints": endpoint_records})
    _write_json(REFUSALS_OUTPUT, {"endpoint_promotion_refusals": refusals})
    _write_json(SCHEMA_OUTPUT, schema)
    _write_text(REPORT_OUTPUT, report)

    return {
        "payload": status_payload,
        "summary": summary,
        "promoted_registry_endpoints": endpoint_records,
        "endpoint_promotion_refusals": refusals,
        "schema": schema,
        "report": report,
    }
