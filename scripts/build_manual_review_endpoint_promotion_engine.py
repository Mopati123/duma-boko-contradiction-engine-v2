#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.manual_review_endpoint_promotion_engine import (
    build_manual_review_endpoint_promotion_engine,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 manual review endpoint promotion records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Preserve strategy candidates for manual review without internet access.",
    )
    mode.add_argument(
        "--verify-endpoints",
        action="store_true",
        help="Attempt live public reachability checks for strategy candidate URLs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "verify-endpoints" if args.verify_endpoints else "dry-run"
    result = build_manual_review_endpoint_promotion_engine(mode=selected_mode)
    print("== Manual Review Endpoint Promotion Engine v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
