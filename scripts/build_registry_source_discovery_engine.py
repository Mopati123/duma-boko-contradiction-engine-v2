#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.registry_source_discovery_engine import (
    build_registry_source_discovery_engine,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 registry source discovery records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Emit deterministic demo source-endpoint candidates without internet access.",
    )
    mode.add_argument(
        "--discover-web",
        action="store_true",
        help="Attempt public registry endpoint discovery using accessible web mechanisms.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "discover-web" if args.discover_web else "dry-run"
    result = build_registry_source_discovery_engine(mode=selected_mode)
    print("== Registry Source Discovery Engine v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
