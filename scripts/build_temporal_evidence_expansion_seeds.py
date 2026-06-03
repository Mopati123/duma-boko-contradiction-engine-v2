#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.temporal_evidence_expansion_seeds import (
    build_temporal_evidence_expansion_seeds,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 temporal evidence expansion seeds."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate temporal expansion inputs without generating seeds.",
    )
    mode.add_argument(
        "--generate",
        action="store_true",
        help="Generate deterministic temporal discovery seeds.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "generate" if args.generate else "dry-run"
    result = build_temporal_evidence_expansion_seeds(mode=selected_mode)
    print("== Temporal Evidence Expansion Seeds v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
