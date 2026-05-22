#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: ./scripts/search_repo.sh '<search text>'"
  exit 1
fi

QUERY="$*"

echo "== Search query =="
echo "$QUERY"
echo

echo "== Matching files/content =="
rg --line-number --hidden \
  --glob '!/.git/' \
  --glob '!/.venv/' \
  --glob '!__pycache__/' \
  --glob '!outputs/reports/*.docx' \
  "$QUERY" .
