#!/usr/bin/env python3
"""
Build candidate-only canonical six-block case models.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.canonical_case_model import build_canonical_case_models


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build candidate-only canonical six-block case models."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run diagnostics only. This is the default behavior.",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Do not perform network access. This lane never uses network access.",
    )
    parser.add_argument(
        "--case-id",
        help="Build one canonical case model by case ID.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_canonical_case_models(
        case_id=args.case_id,
        no_network=args.no_network,
    )

    print("== Canonical 6-Block Case Model v1 summary ==")
    print("Mode: dry-run")
    print("network: disabled")
    if args.case_id:
        print(f"case_id: {args.case_id}")
    print(f"case_model_count: {summary['case_model_count']}")
    print(f"six_block_complete_count: {summary['six_block_complete_count']}")
    print(f"content_review_candidate_count: {summary['content_review_candidate_count']}")
    print(f"requires_manual_review_count: {summary['requires_manual_review_count']}")
    print(f"approved_evidence: {summary['approved_evidence']}")
    print(f"public_ready: {summary['public_ready']}")
    print(f"institutional_ready: {summary['institutional_ready']}")
    print(f"report_ready: {summary['report_ready']}")
    print(f"case_ids: {', '.join(summary['case_ids'])}")
    for case, category in sorted(summary["case_categories"].items()):
        print(f"{case}_category: {category}")
    for case, status in sorted(summary["case_statuses"].items()):
        print(f"{case}_status: {status}")
    print(f"models_output: {summary['models_output']}")
    print(f"summary_output: {summary['summary_output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
