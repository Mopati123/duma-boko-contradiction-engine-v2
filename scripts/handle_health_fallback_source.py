#!/usr/bin/env python3
"""
Handle candidate-only fallback source diagnostics for VID_HEALTH_001.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.health_fallback_source import handle_health_fallback_source


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run candidate-only health fallback source handling."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run diagnostics only. This is the default behavior.",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Avoid live web requests and mark fallback for manual review.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=10,
        help="Timeout for the lightweight HTTP request.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = handle_health_fallback_source(
        no_network=args.no_network,
        timeout_seconds=args.timeout_seconds,
    )

    print("== Health Fallback Source v1 summary ==")
    print("Mode: dry-run")
    if args.no_network:
        print("network: disabled")
    else:
        print("network: lightweight")
    print(f"total_records: {summary['total_records']}")
    print(f"fallback_candidate_id: {summary['fallback_candidate_id']}")
    print(f"fallback_extraction_status: {summary['fallback_extraction_status']}")
    print(f"fallback_verification_status: {summary['fallback_verification_status']}")
    print(f"fallback_selected_count: {summary['fallback_selected_count']}")
    print(f"fallback_blocked_count: {summary['fallback_blocked_count']}")
    print(f"fallback_unavailable_count: {summary['fallback_unavailable_count']}")
    print(f"fallback_error_count: {summary['fallback_error_count']}")
    print(f"extracted_candidate_count: {summary['extracted_candidate_count']}")
    print(f"not_checked_count: {summary['not_checked_count']}")
    print(
        "verified_candidate_for_content_review_count: "
        f"{summary['verified_candidate_for_content_review_count']}"
    )
    print(
        "verified_for_content_review_count: "
        f"{summary['verified_for_content_review_count']}"
    )
    print(f"requires_manual_review_count: {summary['requires_manual_review_count']}")
    print(f"approved_evidence: {summary['approved_evidence']}")
    print(f"public_ready: {summary['public_ready']}")
    print(f"institutional_ready: {summary['institutional_ready']}")
    print(f"report_ready: {summary['report_ready']}")
    print(f"status_output: {summary['status_output']}")
    print(f"summary_output: {summary['summary_output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
