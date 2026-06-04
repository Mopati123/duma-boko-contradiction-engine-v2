#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.deep_research_temporal_metadata_pack import (
    build_deep_research_temporal_metadata_pack,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 deep research temporal metadata pack records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate deep research temporal URL candidate shape only.",
    )
    mode.add_argument(
        "--extract-pack",
        action="store_true",
        help="Extract a reviewable temporal metadata pack without URL validation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "extract-pack" if args.extract_pack else "dry-run"
    result = build_deep_research_temporal_metadata_pack(mode=selected_mode)
    print("== Deep Research Temporal Metadata Pack v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
