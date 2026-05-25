#!/usr/bin/env python3
"""
Verify extracted source-content candidates without approving evidence.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.source_content_verification import verify_source_content


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run candidate-only source content verification."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run diagnostics only. This is the default behavior.",
    )
    parser.add_argument(
        "--evidence-id",
        help="Verify source-content diagnostics for one original evidence ID.",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Do not fetch anything. Verification only inspects existing diagnostics.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = verify_source_content(
        evidence_id=args.evidence_id,
        no_network=args.no_network,
    )

    print("== Source Content Verification v1 summary ==")
    print("Mode: dry-run")
    print("network: disabled")
    if args.evidence_id:
        print(f"evidence_id: {args.evidence_id}")
    print(f"artifact_found: {summary['artifact_found']}")
    print(f"total_records: {summary['total_records']}")
    print(
        "verified_candidate_for_content_review_count: "
        f"{summary['verified_candidate_for_content_review_count']}"
    )
    print(
        "verified_for_content_review_count: "
        f"{summary['verified_for_content_review_count']}"
    )
    print(f"blocked_pending_fallback_count: {summary['blocked_pending_fallback_count']}")
    print(f"extraction_unavailable_count: {summary['extraction_unavailable_count']}")
    print(f"not_checked_count: {summary['not_checked_count']}")
    print(f"error_count: {summary['error_count']}")
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
