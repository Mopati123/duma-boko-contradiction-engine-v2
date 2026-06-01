#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.contradiction_graph_engine import build_contradiction_graph_engine


def parse_args():
    parser = argparse.ArgumentParser(description="Build v2 contradiction graph records.")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run only.")
    return parser.parse_args()


def main() -> int:
    parse_args()
    result = build_contradiction_graph_engine()
    print("== Contradiction Graph Engine v2 summary ==")
    print("Mode: dry-run")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
