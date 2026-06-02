#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.canonical_source_registry_engine import (
    build_canonical_source_registry_engine,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 canonical source registry records."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate deterministic registry sources without harvesting.",
    )
    return parser.parse_args()


def main() -> int:
    parse_args()
    result = build_canonical_source_registry_engine(mode="dry-run")
    print("== Canonical Source Registry Engine v2 summary ==")
    print("Mode: dry-run")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
