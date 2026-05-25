# Real Evidence Input Templates

These templates are placeholders for human-entered evidence data.

They are not verified evidence, approved evidence, public evidence, or release-ready evidence.

Use these files to enter only human-verified source transcript, timestamp, quote, speaker,
context, case relevance, and reviewer notes. Do not fabricate transcript text, quotes,
timestamps, or context.

The default `verification_status` is `pending_human_entry`.

Allowed `verification_status` values:

- `pending_human_entry`
- `entered_pending_review`
- `rejected_do_not_use`
- `verified_for_approval_review`

`verified_for_approval_review` means the record is ready for Real Evidence Approval v1
review only. It does not mark evidence as public-ready, institution-ready, or report-ready.
