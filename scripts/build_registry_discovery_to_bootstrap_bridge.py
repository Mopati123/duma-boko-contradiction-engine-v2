#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.registry_discovery_to_bootstrap_bridge import (
    build_registry_discovery_to_bootstrap_bridge,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 registry discovery to bootstrap bridge candidates."
    )
    parser.add_argument(
        "--from-promotions",
        action="store_true",
        help="Convert verified promoted endpoints into registry update candidates.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.from_promotions:
        raise ValueError("Select --from-promotions")
    result = build_registry_discovery_to_bootstrap_bridge(mode="from-promotions")
    print("== Registry Discovery to Bootstrap Bridge v2 summary ==")
    print("Mode: from-promotions")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
