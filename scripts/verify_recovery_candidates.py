#!/usr/bin/env python3
"""
Verify source recovery candidates without approving evidence.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.recovery_candidate_verification import verify_recovery_candidates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run conservative recovery-candidate reachability diagnostics."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run diagnostics only. This is the default behavior.",
    )
    parser.add_argument(
        "--candidate-id",
        help="Verify only one recovery candidate ID.",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Avoid live web requests and mark candidates for manual review.",
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
    summary = verify_recovery_candidates(
        candidate_id=args.candidate_id,
        no_network=args.no_network,
        timeout_seconds=args.timeout_seconds,
    )

    print("== Recovery Candidate Verification v1 summary ==")
    print("Mode: dry-run")
    if args.no_network:
        print("network: disabled")
    else:
        print("network: lightweight")
    if args.candidate_id:
        print(f"candidate_id: {args.candidate_id}")
    print(f"total_candidates: {summary['total_candidates']}")
    print(f"reachable_candidates: {summary['reachable_candidates']}")
    print(f"blocked_candidates: {summary['blocked_candidates']}")
    print(f"unreachable_candidates: {summary['unreachable_candidates']}")
    print(f"error_candidates: {summary['error_candidates']}")
    print(f"not_checked_candidates: {summary['not_checked_candidates']}")
    print(f"candidate_content_found: {summary['candidate_content_found']}")
    print(f"requires_manual_review: {summary['requires_manual_review']}")
    print(f"verified_for_manual_review: {summary['verified_for_manual_review']}")
    print(f"approved_evidence: {summary['approved_evidence']}")
    print(f"public_ready: {summary['public_ready']}")
    print(f"institutional_ready: {summary['institutional_ready']}")
    print(f"report_ready: {summary['report_ready']}")
    print(f"status_output: {summary['status_output']}")
    print(f"summary_output: {summary['summary_output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
