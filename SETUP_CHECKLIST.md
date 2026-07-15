# Setup checklist — Airtable-triggered lead-scraper routine

Two people, split by who owns what. **You (Abu)** do steps 1–3 and 6. **Your boss** (whose Claude
account will host the routine) does steps 4–5. ~30–40 min total, one time.

---

## YOU — Step 1: Create the repo (company GitHub)

1. Create a private repo in the company org, e.g. `company/lead-scraper-routine`.
2. Push the contents of this folder to it (scripts/, assets/, references/, SKILL.md,
   ROUTINE_PROMPT.md, README.md). **Do NOT commit any API keys** — there are none in these files;
   keep it that way.
3. Note the repo URL — your boss needs it for step 4.

## YOU — Step 2: Have the Claude GitHub App authorized on the repo

The routine clones the repo, so your boss's Claude environment needs read access. A company
GitHub **org admin** installs the Claude GitHub App (https://github.com/apps/claude) on the org
or specifically on this repo. (If your boss's account already has it on the org, skip.)

## YOU — Step 3: Build the Airtable intake (form + automation)

In the Airtable base that will hold the form:

1. Create a table **Lead Requests** with fields:
   - `Count` (Number, integer)
   - `Location` (Single line text) — e.g. "Berlin, Germany"
   - `Industry` (Single line text) — e.g. "marketing agency"
   - `Country code` (Single line text, optional; default "de")
   - `Status` (Single select: Requested / Running / Done) — optional, nice for tracking
2. Create a **Form view** on that table exposing Count, Location, Industry (+ Country code).
3. Add an **Automation**: trigger "When a record is created" on Lead Requests →
   action "Run a script" using `airtable_automation.js` from this repo. Paste the routine's
   **Fire URL** and **token** into the two constants at the top (your boss gives you these after
   step 5). The script POSTs `{count, location, industry}` to the routine.

## BOSS — Step 4: Create the routine in your Claude account

In your Claude account, at https://claude.ai/code (or have Abu drive with the `routines` skill
pointed at your environment ID):

1. Get your **environment ID** from https://claude.ai/code/environments (`env_01...`).
2. Create a routine with:
   - **Repo source**: the company repo URL from step 1
   - **Model**: claude-sonnet-4-6
   - **Tools**: Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch
   - **Prompt**: paste the entire contents of `ROUTINE_PROMPT.md`
   - **Schedule**: none needed (this is webhook-driven) — or a dummy far-future cron; the API
     trigger is what matters.

## BOSS — Step 5: Add the API trigger + secrets

1. Open the routine → edit → **Add another trigger → API → Generate token**. Copy the **Fire URL**
   and **token** (shown once). Give both to Abu for step 3.
2. At https://claude.ai/code/environments, add these secrets to the environment the routine uses:
   - `APIFY_TOKEN` = company Apify token
   - `SERPER_API_KEY` = company Serper key
   - `MILLIONVERIFIER_API_KEY` = company MV key (optional)
   - `GSHEET_ID` = `1ldfNyghlKqriE1aEHFCSUBMjikgj5zrMX_1FBcGvksk`
   - `GSHEET_GID` = `1347092156`
   - `GOOGLE_SERVICE_ACCOUNT_JSON` = the *entire contents* of the Google service-account JSON key
     file (one line is fine). The target Google Sheet must be shared with that service account's
     `client_email` as Editor.

## YOU — Step 6: Test end to end

1. Submit the Airtable form with a small request (Count 10, a real city, a clear industry).
2. Watch the run at `https://claude.ai/code/scheduled` (your boss may need to share access, or
   test from their account).
3. Confirm rows land in the master Google Sheet and the summary looks honest.

---

### Notes

- **Billing**: Apify/Serper/MV usage bills to whichever company accounts those keys belong to,
  regardless of whose Claude account hosts the routine.
- **Cost per run** is bounded by the 2.5×/max-150 volume cap in `routine_run.py` — a 20-lead
  request fetches ~50 raw, not hundreds.
- **Cloud limits**: the routine has no local files or local MCP — only the cloned repo and the
  secrets. That's why keys are env vars and the Sheet uses a service account (no browser login).
