#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "== Local CI: v3 divergence validation =="
echo "Repo: $(pwd)"
echo

echo "== Git status before test =="
git status --short
if [ -n "$(git status --short)" ]; then
  echo "ERROR: Working tree must be clean before running local CI."
  exit 1
fi

echo
echo "== Python environment =="
python --version
which python

echo
echo "== Running canonical v3 test =="
python test_v3_divergence_pipeline.py

echo
echo "== Cleaning generated tracked artifacts =="
git restore outputs/cases/divergence_cases.json
git restore outputs/reports/DUMA_BOKO_FINAL_FORENSIC_REPORT.docx

echo
echo "== Removing ignored dated report artifacts =="
git clean -fX outputs/reports/

echo
echo "== Git status after cleanup =="
git status --short
if [ -n "$(git status --short)" ]; then
  echo "ERROR: Working tree is not clean after local CI."
  git status
  exit 1
fi

echo
echo "== LOCAL CI PASSED =="
