# Real URL Insertion Guide

## Purpose

This guide explains how Papas can move discovery seeds from unresolved investigation targets to real candidate public sources without inventing evidence. This workflow does not add quotes, timestamps, transcripts, approved evidence, public readiness, institutional readiness, production readiness, or contradiction claims.

## Source File To Edit

Open:

```text
inputs/evidence_discovery/duma_boko_discovery_seeds.json
```

## URL Insertion Rules

Replace only selected `UNSPECIFIED` `candidate_url` values with verified public URLs.

For every inserted URL, preserve the surrounding seed fields:

```text
candidate_url
candidate_title
platform
source_type
speaker_name
expected_topic
expected_claim_keywords
notes
```

Do not change the topic or keyword context merely to fit a URL. If a URL does not clearly belong to the seed topic, leave the seed unresolved and keep `candidate_url` as `UNSPECIFIED`.

## Prohibited In This Step

Do not add quotes yet.

Do not add timestamps yet.

Do not add transcript lines yet.

Do not claim contradictions yet.

Do not insert fake sources.

Do not mark evidence approved.

Do not set `production_ready`, `public_ready`, or `institutional_ready` to true.

## Validation Commands

After verified public URLs are inserted, run:

```bash
python scripts/build_discovery_seed_pack_loader.py --dry-run
python scripts/build_evidence_discovery_execution_engine.py --from-seeds
```

## Expected Result After Real URLs Exist

```text
resolved_source_count > 0
refusal_count may remain > 0
quotes_created = 0
timestamps_created = 0
contradictions_created = 0
production_ready = False
approved_evidence = 0
```

## Manual Review Notes

Resolved candidate sources remain manual-review targets. A resolved URL only means the discovery execution engine can carry the source forward for metadata and evidence gathering. It does not prove a quote, timestamp, promise, current position, contradiction, or readiness status.

The next manual step for Papas is to replace selected `UNSPECIFIED` `candidate_url` fields with verified public URLs only.
