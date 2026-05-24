# Release Policy v1

## Purpose

Release Policy v1 defines when local CI may temporarily act as the validation authority while GitHub Actions is unavailable. It does not approve evidence for public release, institutional release, or report-ready status.

## Scope

This policy applies to repository validation for the Duma Boko promise-delivery divergence engine while GitHub Actions jobs are blocked before repository code executes. It covers manual merge override decisions for unavailable remote CI only.

This policy does not approve:

- public evidence release
- institutional evidence release
- report_ready promotion
- public_ready promotion
- institutional_ready promotion
- live transcript acquisition
- public final report generation

## Current GitHub Actions Limitation

GitHub Actions is unavailable when the remote job does not start because the account is locked due to a billing issue. In that state, the job has zero steps, `runner_id` is `0`, `runner_name` is empty, and repository code is not executed.

## Local CI Authority

Local CI may temporarily act as the validation authority only for repository validation replacement while GitHub Actions is unavailable. Local CI authority does not replace evidence approval, source approval, transcript approval, timestamp approval, quote approval, context approval, reviewer approval, public release approval, institutional release approval, or report-ready approval.

## Manual Override Eligibility

Manual override is allowed only when all are true:

- local CI passed
- working tree is clean
- branch is pushed
- GitHub Actions did not execute repository code
- remote job had zero steps
- runner_id is 0
- runner_name is empty
- error is external billing/account lock
- no repository/test/interpreter/dependency failure occurred

## Manual Override Non-Eligibility

Manual override is not allowed when any are true:

- any repository command ran and failed
- any test failed
- any Python interpreter error occurred
- any dependency installation failed
- any lint/type/schema gate failed
- branch has uncommitted changes
- generated artifacts remain uncleaned
- evidence is being promoted to public_ready/report_ready without approval

## Required Diagnostic Evidence

A manual override record must include:

- GitHub Actions run metadata
- failed check name
- failed job URL
- annotations showing the billing/account lock message
- step count showing zero steps
- runner_id showing `0`
- runner_name showing an empty value
- PR state and branch names
- local branch status

## Required Local Validation Evidence

A manual override record must include:

- local CI command used
- local CI passed output
- clean working tree before local CI
- clean working tree after local CI cleanup
- latest commits
- confirmation generated artifacts were cleaned
- confirmation no live transcript acquisition ran
- confirmation no readiness promotion occurred

## Prohibited Claims

Manual override may not claim:

- public readiness
- institutional readiness
- report readiness
- validated public evidence
- public-ready evidence
- institution-ready evidence
- final forensic report readiness

## Release Blockers

The report remains blocked from public or institutional release until real evidence, manual review, source verification, timestamp verification, quote verification, context verification, reviewer approval, and release policy approval are complete.

## Reviewer Responsibility

The reviewer must confirm that the override is a CI availability override only. The reviewer must not treat local CI success as evidence approval or release approval.

## Future Restoration Path

When GitHub Actions availability is restored, remote CI must resume as the normal validation authority. Manual override must no longer be used for PRs where GitHub Actions executes repository code and fails for repository, test, interpreter, dependency, lint, type, or schema reasons.
