#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f ".venv/bin/activate" ]; then
  source ".venv/bin/activate"
else
  echo "ERROR: .venv not found. Create it with:"
  echo "python3 -m venv .venv"
  echo "source .venv/bin/activate"
  echo "pip install -r requirements.txt"
  exit 1
fi

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
echo "== Building evidence index =="
python scripts/build_evidence_index.py

echo
echo "== Inspecting evidence sources =="
python scripts/inspect_evidence_sources.py

echo
echo "== Validating transcript acquisition fixtures =="
python scripts/acquire_transcripts.py --fixtures-only

echo
echo "== Validating timestamp verification fixtures =="
python scripts/verify_timestamps.py --fixtures-only

echo
echo "== Validating quote verification fixtures =="
python scripts/verify_quotes.py --fixtures-only

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
echo "== Removing ignored evidence index artifacts =="
if [ -d outputs/evidence ]; then
  git clean -fX outputs/evidence/
fi

echo
echo "== Removing ignored transcript acquisition artifacts =="
git clean -fX data/evidence_transcripts/

echo
echo "== Removing ignored timestamp verification artifacts =="
if [ -d outputs/timestamps ]; then
  git clean -fX outputs/timestamps/
fi

echo
echo "== Removing ignored quote verification artifacts =="
if [ -d outputs/quotes ]; then
  git clean -fX outputs/quotes/
fi

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
