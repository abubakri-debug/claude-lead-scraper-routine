# lead-scraper-routine

Automated founder-level B2B lead generation. Fill an Airtable form (count, location, industry) →
a Claude cloud routine scrapes, verifies, ICP-scores, and appends qualified leads to a master
Google Sheet.

## What's here

- `SKILL.md` — the full pipeline method (also usable as a local Claude skill).
- `scripts/` — the pipeline (discovery, enrichment, founder ID, registry checks, ICP export,
  email verification, Google Sheets append). Stdlib-only except `openpyxl` and `google-auth`.
- `assets/icp-default.json` — the ICP definition used for scoring (edit to retune).
- `references/` — actor catalog, cost guardrails, registry notes.
- `ROUTINE_PROMPT.md` — the prompt that drives the routine on each webhook fire.
- `airtable_automation.js` — the Airtable "Run a script" action that fires the routine.
- `SETUP_CHECKLIST.md` — step-by-step setup, split between you and the routine owner.

## Setup

Follow `SETUP_CHECKLIST.md`. In short: push this repo → authorize the Claude GitHub App on it →
build the Airtable form + automation → routine owner creates the routine (prompt = ROUTINE_PROMPT.md),
generates the API trigger token, and adds the API keys as cloud-environment secrets.

## Run it locally instead (no routine)

The pipeline also runs as a normal Claude skill — drop the folder in `~/.claude/skills/` and ask
Claude for leads. See `SKILL.md`. Keys via `scripts/env_loader.py`.

## Secrets (never commit)

`APIFY_TOKEN`, `SERPER_API_KEY`, `MILLIONVERIFIER_API_KEY` (optional), `GSHEET_ID`, `GSHEET_GID`,
`GOOGLE_SERVICE_ACCOUNT_JSON`. In the cloud routine these are environment secrets; locally they
live in `~/.claude/lead-scraper.env`.
