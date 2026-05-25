#!/usr/bin/env python3
"""
Extract candidate text from selected recovery sources without approving evidence.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.source_content_extraction import extract_selected_source_content


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run candidate-only source content extraction."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run diagnostics only. This is the default behavior.",
    )
    parser.add_argument(
        "--evidence-id",
        help="Extract candidate content for one original evidence ID.",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Avoid live web requests and mark sources for manual review.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=10,
        help="Timeout for each lightweight HTTP request.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = extract_selected_source_content(
        evidence_id=args.evidence_id,
        no_network=args.no_network,
        timeout_seconds=args.timeout_seconds,
    )

    print("== Source Content Extraction v1 summary ==")
    print("Mode: dry-run")
    if args.no_network:
        print("network: disabled")
    else:
        print("network: lightweight")
    if args.evidence_id:
        print(f"evidence_id: {args.evidence_id}")
    print(f"total_sources: {summary['total_sources']}")
    print(f"extracted_candidate_count: {summary['extracted_candidate_count']}")
    print(f"extraction_unavailable_count: {summary['extraction_unavailable_count']}")
    print(f"blocked_count: {summary['blocked_count']}")
    print(f"error_count: {summary['error_count']}")
    print(f"not_checked_count: {summary['not_checked_count']}")
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
