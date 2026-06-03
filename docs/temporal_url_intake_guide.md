# Temporal URL Intake Guide

## Purpose

This guide explains how Papas can paste verified temporal source URLs into a structured intake template before the curated temporal source pack is updated. This lane validates supplied URLs only. It does not search the web, invent sources, create quotes, timestamps, claims, contradictions, approved evidence, or production readiness.

## Source File To Edit

Open:

```text
inputs/temporal_sources/verified_temporal_url_intake_template.json
```

Edit only the records inside:

```text
verified_temporal_url_intake
```

## Required Fields

Every intake record must keep these fields:

```text
source_id
time_direction
source_type
url
title
publisher
published_date
topic
linked_claim_id
verification_notes
```

Preserve the `source_id`, `time_direction`, `source_type`, `topic`, and `linked_claim_id` from the existing curated temporal source slot. Replace `url`, `title`, `publisher`, `published_date`, and `verification_notes` only when a real public source has been verified.

## URL Rules

Use only public `http` or `https` URLs that you have personally verified in a browser.

Do not paste Google, DuckDuckGo, Bing, YouTube search, Facebook search, or other search-result pages as source URLs.

Leave unresolved slots as:

```json
"url": "UNSPECIFIED"
```

An `UNSPECIFIED` URL will be refused by validation until a real public URL is supplied.

## Prohibited In This Step

Do not add quotes.

Do not add timestamps.

Do not add transcript lines.

Do not create claims.

Do not claim contradictions.

Do not insert fake sources.

Do not mark evidence approved.

Do not set production readiness to true.

## Validation Commands

After editing the intake template, run:

```bash
python scripts/build_verified_temporal_url_intake.py --dry-run
python scripts/build_verified_temporal_url_intake.py --validate-intake
```

## Expected Result Before URLs Are Added

```text
validated_url_count = 0
refusal_count = 11
refusal_code = REFUSED_UNSPECIFIED_URL
urls_invented = 0
quotes_created = 0
timestamps_created = 0
claims_created = 0
contradictions_created = 0
production_ready = False
approved_evidence = 0
```

## Expected Result After Real URLs Exist

```text
validated_url_count > 0
refusal_count may remain > 0
urls_invented = 0
quotes_created = 0
timestamps_created = 0
claims_created = 0
contradictions_created = 0
production_ready = False
approved_evidence = 0
```

Validated intake URLs remain manual-review candidates. A validated URL only means the intake lane can carry the supplied source forward to the next lane that applies temporal URLs to the curated source pack.
