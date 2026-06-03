#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.curated_temporal_url_population_assistant import (
    build_curated_temporal_url_population_assistant,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 curated temporal URL population assistant records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate UNSPECIFIED temporal slots without candidate search.",
    )
    mode.add_argument(
        "--search-candidates",
        action="store_true",
        help="Search for manual-review candidate URLs for UNSPECIFIED temporal slots.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "search-candidates" if args.search_candidates else "dry-run"
    result = build_curated_temporal_url_population_assistant(mode=selected_mode)
    print("== Curated Temporal URL Population Assistant v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
