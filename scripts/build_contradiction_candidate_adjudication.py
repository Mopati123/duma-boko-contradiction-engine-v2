#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.contradiction_candidate_adjudication import (
    build_contradiction_candidate_adjudication,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 contradiction candidate adjudication."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate relationship graph edges without adjudicating candidates.",
    )
    mode.add_argument(
        "--adjudicate",
        action="store_true",
        help="Adjudicate relationship graph edges into candidate statuses.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "adjudicate" if args.adjudicate else "dry-run"
    result = build_contradiction_candidate_adjudication(mode=selected_mode)
    print("== Contradiction Candidate Adjudication v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
