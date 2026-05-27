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
echo "== Validating case evidence linking fixtures =="
python scripts/link_case_evidence.py --fixtures-only

echo
echo "== Validating report section assembly fixtures =="
python scripts/assemble_report_sections.py --fixtures-only

echo
echo "== Validating final report generation fixtures =="
python scripts/generate_final_report_v1.py --fixtures-only

echo
echo "== Validating real evidence replacement dry-run =="
python scripts/replace_real_evidence.py --dry-run

echo
echo "== Validating manual review dry-run =="
python scripts/manual_review.py --dry-run

echo
echo "== Validating final report hardening dry-run =="
python scripts/harden_final_report.py --dry-run

echo
echo "== Validating release readiness dry-run =="
python scripts/check_release_readiness.py --dry-run

echo
echo "== Validating release policy dry-run =="
python scripts/check_release_policy.py --dry-run

echo
echo "== Validating real evidence population inputs =="
python scripts/validate_real_evidence_inputs.py --dry-run

echo
echo "== Validating recovery candidate verification no-network =="
python scripts/verify_recovery_candidates.py --no-network

echo
echo "== Validating selected source content extraction no-network =="
python scripts/extract_selected_source_content.py --no-network

echo
echo "== Validating source content verification no-network =="
python scripts/verify_source_content.py --no-network

echo
echo "== Validating health fallback source no-network =="
python scripts/handle_health_fallback_source.py --no-network

echo
echo "== Validating canonical six-block case models no-network =="
python scripts/build_canonical_case_models.py --no-network

echo
echo "== Validating explicit template reconciliation action dry-run =="
python scripts/apply_template_reconciliation.py --dry-run

echo
echo "== Validating template update from content review dry-run =="
python scripts/update_templates_from_content_review.py --dry-run

echo
echo "== Validating manual review promotion dry-run =="
python scripts/promote_manual_review.py --dry-run

echo
echo "== Validating exact evidence field completion dry-run =="
python scripts/complete_exact_evidence_fields.py --dry-run

echo
echo "== Validating exact quote manual entry examples reject =="
python scripts/apply_exact_quote_manual_entry.py --entry-file data/manual_evidence_entries/VID_JOBS_001.entry.example.json --dry-run --expect-rejected
python scripts/apply_exact_quote_manual_entry.py --entry-file data/manual_evidence_entries/VID_HEALTH_001.entry.example.json --dry-run --expect-rejected

echo
echo "== Validating real evidence approval dry-run =="
python scripts/approve_real_evidence.py --dry-run

echo
echo "== Validating final approved evidence packet dry-run =="
python scripts/generate_final_approved_packet.py --dry-run

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
echo "== Removing ignored case evidence linking artifacts =="
if [ -d outputs/case_links ]; then
  git clean -fX outputs/case_links/
fi

echo
echo "== Removing ignored report section assembly artifacts =="
if [ -d outputs/report_sections ]; then
  git clean -fX outputs/report_sections/
fi

echo
echo "== Removing ignored final report v1 artifacts =="
if [ -d outputs/final_report ]; then
  git clean -fX outputs/final_report/
fi

echo
echo "== Removing ignored real evidence replacement artifacts =="
if [ -d outputs/real_evidence ]; then
  git clean -fX outputs/real_evidence/
fi

echo
echo "== Removing ignored manual review artifacts =="
if [ -d outputs/manual_review ]; then
  git clean -fX outputs/manual_review/
fi

echo
echo "== Removing ignored final report hardening artifacts =="
if [ -d outputs/final_report_hardening ]; then
  git clean -fX outputs/final_report_hardening/
fi

echo
echo "== Removing ignored release readiness artifacts =="
if [ -d outputs/release_readiness ]; then
  git clean -fX outputs/release_readiness/
fi

echo
echo "== Removing ignored release policy artifacts =="
if [ -d outputs/release_policy ]; then
  git clean -fX outputs/release_policy/
fi

echo
echo "== Removing ignored real evidence input artifacts =="
if [ -d outputs/real_evidence_inputs ]; then
  git clean -fX outputs/real_evidence_inputs/
fi

echo
echo "== Removing ignored recovery candidate verification artifacts =="
if [ -d outputs/recovery_candidate_verification ]; then
  git clean -fX outputs/recovery_candidate_verification/
fi

echo
echo "== Removing ignored source content extraction artifacts =="
if [ -d outputs/source_content_extraction ]; then
  git clean -fX outputs/source_content_extraction/
fi

echo
echo "== Removing ignored source content verification artifacts =="
if [ -d outputs/source_content_verification ]; then
  git clean -fX outputs/source_content_verification/
fi

echo
echo "== Removing ignored health fallback source artifacts =="
if [ -d outputs/health_fallback_source ]; then
  git clean -fX outputs/health_fallback_source/
fi

echo
echo "== Removing ignored canonical case model artifacts =="
if [ -d outputs/canonical_case_models ]; then
  git clean -fX outputs/canonical_case_models/
fi

echo
echo "== Removing ignored explicit template reconciliation action artifacts =="
if [ -d outputs/template_reconciliation_action ]; then
  git clean -fX outputs/template_reconciliation_action/
fi

echo
echo "== Removing ignored template update artifacts =="
if [ -d outputs/template_update_from_content_review ]; then
  git clean -fX outputs/template_update_from_content_review/
fi

echo
echo "== Removing ignored manual review promotion artifacts =="
if [ -d outputs/manual_review_promotion ]; then
  git clean -fX outputs/manual_review_promotion/
fi

echo
echo "== Removing ignored exact evidence field completion artifacts =="
if [ -d outputs/exact_evidence_field_completion ]; then
  git clean -fX outputs/exact_evidence_field_completion/
fi

echo
echo "== Removing ignored exact quote manual entry artifacts =="
if [ -d outputs/exact_quote_manual_entry ]; then
  git clean -fX outputs/exact_quote_manual_entry/
fi

echo
echo "== Removing ignored real evidence approval artifacts =="
if [ -d outputs/real_evidence_approval ]; then
  git clean -fX outputs/real_evidence_approval/
fi

echo
echo "== Removing ignored final approved evidence packet artifacts =="
if [ -d outputs/final_approved_packet ]; then
  git clean -fX outputs/final_approved_packet/
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
